"""
SQLAlchemy 2.0 declarative models for Relayd.
All IDs are plain TEXT UUIDs (generated in Python, not by the DB).
JSON/JSONB columns store Python dicts/lists natively via SQLAlchemy's JSON type.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=_uuid)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name          = Column(String)
    role          = Column(String, nullable=False, default="user")
    created_at    = Column(DateTime(timezone=True), default=_now)

    domains       = relationship("Domain", back_populates="user", cascade="all, delete-orphan")
    mailboxes     = relationship("Mailbox", back_populates="user", cascade="all, delete-orphan")
    aliases       = relationship("Alias", back_populates="user", cascade="all, delete-orphan")
    relays        = relationship("Relay", back_populates="user", cascade="all, delete-orphan")
    delivery_logs = relationship("DeliveryLog", back_populates="user", cascade="all, delete-orphan")
    tasks         = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    api_tokens    = relationship("ApiToken", back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------
class Domain(Base):
    __tablename__ = "domains"

    id               = Column(String, primary_key=True, default=_uuid)
    user_id          = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name             = Column(String, nullable=False, index=True)
    dkim_selector    = Column(String, default="mail")
    mail_host        = Column(String, default="mail")
    dkim_private_key = Column(Text)
    dkim_public_key  = Column(Text)
    verified         = Column(Boolean, default=False)
    score            = Column(Integer, default=0)
    checks           = Column(JSONB, default=dict)
    last_checked_at  = Column(DateTime(timezone=True))
    created_at       = Column(DateTime(timezone=True), default=_now)

    user      = relationship("User", back_populates="domains")
    mailboxes = relationship("Mailbox", back_populates="domain_rel", cascade="all, delete-orphan")
    aliases   = relationship("Alias", back_populates="domain_rel", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Mailboxes
# ---------------------------------------------------------------------------
class Mailbox(Base):
    __tablename__ = "mailboxes"

    id            = Column(String, primary_key=True, default=_uuid)
    user_id       = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    domain_id     = Column(String, ForeignKey("domains.id", ondelete="CASCADE"))
    domain        = Column(String, nullable=False)
    local_part    = Column(String, nullable=False)
    address       = Column(String, unique=True, nullable=False, index=True)
    display_name  = Column(String)
    password_hash = Column(String, nullable=False)
    quota_mb      = Column(Integer, default=1024)
    active        = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), default=_now)

    user       = relationship("User", back_populates="mailboxes")
    domain_rel = relationship("Domain", back_populates="mailboxes")


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------
class Alias(Base):
    __tablename__ = "aliases"

    id           = Column(String, primary_key=True, default=_uuid)
    user_id      = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    domain_id    = Column(String, ForeignKey("domains.id", ondelete="CASCADE"))
    domain       = Column(String, nullable=False)
    local_part   = Column(String, nullable=False)
    address      = Column(String, unique=True, nullable=False, index=True)
    catch_all    = Column(Boolean, default=False)
    destinations = Column(JSONB, default=list)
    enabled      = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), default=_now)

    user       = relationship("User", back_populates="aliases")
    domain_rel = relationship("Domain", back_populates="aliases")


# ---------------------------------------------------------------------------
# Relays
# ---------------------------------------------------------------------------
class Relay(Base):
    __tablename__ = "relays"

    id            = Column(String, primary_key=True, default=_uuid)
    user_id       = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name          = Column(String, nullable=False)
    type          = Column(String, nullable=False)
    config        = Column(JSONB, default=dict)
    priority      = Column(Integer, default=100)
    is_default    = Column(Boolean, default=False)
    enabled       = Column(Boolean, default=True)
    daily_quota   = Column(Integer, default=0)
    weight        = Column(Integer, default=100)
    usage_today   = Column(Integer, default=0)
    usage_date    = Column(String)
    health_status = Column(String, default="healthy")
    match_domains = Column(JSONB, default=list)
    match_tags    = Column(JSONB, default=list)
    created_at    = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="relays")


# ---------------------------------------------------------------------------
# Delivery Logs
# ---------------------------------------------------------------------------
class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id            = Column(String, primary_key=True, default=_uuid)
    user_id       = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_email    = Column(String, nullable=False)
    to_email      = Column(String, nullable=False)   # NOTE: 'to' is a SQL keyword — using to_email
    subject       = Column(String)
    status        = Column(String, nullable=False, index=True)
    provider_id   = Column(String)
    provider_name = Column(String)
    provider_type = Column(String)
    message_id    = Column(String)
    error         = Column(Text)
    attempts      = Column(JSONB, default=list)
    created_at    = Column(DateTime(timezone=True), default=_now, index=True)

    user = relationship("User", back_populates="delivery_logs")


# ---------------------------------------------------------------------------
# Tasks  (background queue — merges old tasks + send_queue collections)
# ---------------------------------------------------------------------------
class Task(Base):
    __tablename__ = "tasks"

    id          = Column(String, primary_key=True, default=_uuid)
    user_id     = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type        = Column(String, nullable=False)
    status      = Column(String, nullable=False, default="pending", index=True)
    payload     = Column(JSONB, default=dict)
    priority    = Column(Integer, default=100)
    attempts    = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_run    = Column(DateTime(timezone=True), default=_now, index=True)
    result      = Column(JSONB)
    last_error  = Column(Text)
    created_at  = Column(DateTime(timezone=True), default=_now)
    updated_at  = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    user = relationship("User", back_populates="tasks")


# ---------------------------------------------------------------------------
# API Tokens
# ---------------------------------------------------------------------------
class ApiToken(Base):
    __tablename__ = "api_tokens"

    id           = Column(String, primary_key=True, default=_uuid)
    user_id      = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token        = Column(String, unique=True, nullable=False, index=True)
    name         = Column(String)
    last_used_at = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="api_tokens")


# ---------------------------------------------------------------------------
# Login Attempts  (brute-force rate limiting — no FK, ephemeral)
# ---------------------------------------------------------------------------
class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    identifier   = Column(String, primary_key=True)
    count        = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    updated_at   = Column(DateTime(timezone=True), default=_now, onupdate=_now)
