"""Main FastAPI app — Relayd."""
import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import certifi

# Fix for Windows asyncio loop policy — MUST be before any loop is created
if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth import hash_password, verify_password

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("relayd")

# Global placeholders
db = None
client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, client
    
    # Initialize Mongo
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "relayd_db")
    
    # Only use TLS if the URL suggests it (Atlas) or if specifically requested
    use_tls = "mongodb+srv://" in mongo_url or "tls=true" in mongo_url.lower()
    
    ca = certifi.where()
    client = AsyncIOMotorClient(
        mongo_url,
        tls=use_tls,
        tlsCAFile=ca if use_tls else None,
        tlsAllowInvalidCertificates=True,
        connectTimeoutMS=10000,
        serverSelectionTimeoutMS=10000
    )
    db = client[db_name]

    try:
        # Verify connection immediately
        await client.admin.command('ping')
        logger.info("Successfully connected to MongoDB Atlas")

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
            
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        # We don't raise here to allow the app to start (and show health check errors)
        # but the app won't be very useful.

    yield
    
    # Shutdown
    if client:
        client.close()
        logger.info("Closed MongoDB connection")

# App
app = FastAPI(
    title="Relayd",
    version="0.1.0",
    lifespan=lifespan
)

api_router = APIRouter(prefix="/api")

@api_router.get("/")
async def root():
    return {"name": "Relayd", "version": "0.1.0", "status": "ok"}

@api_router.get("/health")
async def health():
    if db is None:
        return {"ok": False, "db": "not_initialized"}
    try:
        await db.command("ping")
        return {"ok": True, "db": "connected"}
    except Exception as e:
        return {"ok": False, "db": str(e)}

# Routers (local imports to ensure 'db' is available via lifespan)
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
    # Use "server:app" string format for reload support
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
