"""
Database setup — SQLAlchemy 2.0 async engine, session factory, and init_db.

Usage in routers:
    from database import get_db
    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

Usage in standalone scripts (worker, inbound):
    from database import get_engine, AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        ...
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from models import Base

logger = logging.getLogger("relayd")

# ---------------------------------------------------------------------------
# Engine — created once at import time from DATABASE_URL env var
# ---------------------------------------------------------------------------
_DATABASE_URL: str | None = None
_engine = None
_AsyncSessionLocal: async_sessionmaker | None = None


def _get_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    # Ensure we use the asyncpg dialect
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def get_engine():
    global _engine, _DATABASE_URL, _AsyncSessionLocal
    url = _get_url()
    if _engine is None or url != _DATABASE_URL:
        _DATABASE_URL = url
        _engine = create_async_engine(
            url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,   # Detect stale connections
            pool_recycle=300,     # Recycle connections every 5 min
        )
        _AsyncSessionLocal = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit (safer for async)
        )
    return _engine


def AsyncSessionLocal() -> AsyncSession:
    """Return a new AsyncSession. Call get_engine() first to initialise."""
    if _AsyncSessionLocal is None:
        get_engine()
    return _AsyncSessionLocal()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request; commit on success, rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Startup — create tables + seed admin user
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """
    Create all tables (safe: CREATE TABLE IF NOT EXISTS via checkfirst=True).
    Seed the admin user from ADMIN_EMAIL / ADMIN_PASSWORD env vars.
    """
    from auth import hash_password, verify_password
    from models import User

    engine = get_engine()

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created / verified")

    # Seed admin
    admin_email    = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from datetime import datetime, timezone

        result = await session.execute(select(User).where(User.email == admin_email))
        existing = result.scalar_one_or_none()

        if existing is None:
            session.add(User(
                id=str(__import__("uuid").uuid4()),
                email=admin_email,
                password_hash=hash_password(admin_password),
                name="Admin",
                role="admin",
                created_at=datetime.now(timezone.utc),
            ))
            await session.commit()
            logger.info("Seeded admin user: %s", admin_email)
        elif not verify_password(admin_password, existing.password_hash):
            existing.password_hash = hash_password(admin_password)
            await session.commit()
            logger.info("Updated admin password from env")


async def check_db() -> bool:
    """Ping the database. Returns True if reachable."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database ping failed: %s", e)
        return False
