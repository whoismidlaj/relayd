"""Main FastAPI app — Email Orchestration Platform."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from auth import hash_password, verify_password

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mailctl")

# Mongo
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# App
app = FastAPI(title="MailCtl — Email Orchestration Platform", version="0.1.0")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"name": "MailCtl", "version": "0.1.0", "status": "ok"}


@api_router.get("/health")
async def health():
    try:
        await db.command("ping")
        return {"ok": True, "db": "connected"}
    except Exception as e:
        return {"ok": False, "db": str(e)}


# Routers
from routers.auth_routes import router as auth_router
from routers.domains import router as domains_router
from routers.mail_routes import router as mail_router
from routers.relay_routes import router as relay_router
from routers.deliverability_routes import router as deliverability_router

api_router.include_router(auth_router)
api_router.include_router(domains_router)
api_router.include_router(mail_router)
api_router.include_router(relay_router)
api_router.include_router(deliverability_router)

app.include_router(api_router)

# CORS — allow cookies from configured frontend origins (preview + localhost)
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
cors_origins = list({
    frontend_url,
    "http://localhost:3000",
    "http://localhost:3001",
})
extra_origins = os.environ.get("CORS_ORIGINS", "").split(",")
for o in extra_origins:
    o = o.strip()
    if o and o != "*":
        cors_origins.append(o)

# Use regex to also allow the deployed preview URL automatically
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.domains.create_index([("user_id", 1), ("name", 1)], unique=True)
    await db.mailboxes.create_index("address", unique=True)
    await db.aliases.create_index("address", unique=True)
    await db.relays.create_index([("user_id", 1), ("name", 1)])
    await db.delivery_logs.create_index([("user_id", 1), ("created_at", -1)])
    await db.login_attempts.create_index("identifier")

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc),
        })
        logger.info("Seeded admin user: %s", admin_email)
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )
        logger.info("Updated admin password from env")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
