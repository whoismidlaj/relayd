"""Main FastAPI app — Relayd."""
import asyncio
import os
import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

# Fix for Windows asyncio loop policy — MUST be before any loop is created
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("relayd")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import init_db, get_engine
    try:
        get_engine()  # validate DATABASE_URL early
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        raise

    yield

    # Shutdown — dispose connection pool
    try:
        from database import get_engine
        await get_engine().dispose()
        logger.info("Database connection pool closed")
    except Exception:
        pass


# App
app = FastAPI(
    title="Relayd",
    version="0.1.0",
    lifespan=lifespan,
)

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"name": "Relayd", "version": "0.1.0", "status": "ok"}


@api_router.get("/health")
async def health():
    from database import check_db
    ok = await check_db()
    return {"ok": ok, "db": "connected" if ok else "unreachable"}


# Routers
from routers import (
    auth_routes, domains, mail_routes, relay_routes,
    deliverability_routes, inbound_routes, token_routes,
    tags_routes, debug_routes, internal_routes,
)

api_router.include_router(auth_routes.router)
api_router.include_router(domains.router)
api_router.include_router(mail_routes.router)
api_router.include_router(relay_routes.router)
api_router.include_router(deliverability_routes.router)
api_router.include_router(inbound_routes.router)
api_router.include_router(token_routes.router)
api_router.include_router(tags_routes.router)
api_router.include_router(debug_routes.router)
api_router.include_router(internal_routes.router)

app.include_router(api_router)

# CORS
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
cors_origins = list({
    frontend_url,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8080",
})
extra_origins = os.environ.get("CORS_ORIGINS", "").split(",")
for o in extra_origins:
    o = o.strip()
    if o and o != "*":
        cors_origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("RELOAD", "false").lower() == "true"
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=reload)
