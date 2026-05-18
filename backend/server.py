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
_global_db = None
db = None
client = None

import sys
from types import ModuleType

class RelaydModule(ModuleType):
    @property
    def db(self):
        import asyncio
        import os
        try:
            loop = asyncio.get_running_loop()
            if hasattr(loop, "_relayd_db"):
                return loop._relayd_db
            
            # Lazy initialize for separate loops (e.g. aiosmtpd threads)
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "relayd_db")
            use_tls = any(x in mongo_url.lower() for x in ["mongodb+srv://", "tls=true", "ssl=true"])
            client_kwargs = {
                "connectTimeoutMS": 30000,
                "serverSelectionTimeoutMS": 30000,
                "heartbeatFrequencyMS": 10000,
                "maxIdleTimeMS": 60000,
                "retryWrites": True,
            }
            if use_tls:
                import certifi
                client_kwargs.update({
                    "tlsCAFile": certifi.where(),
                    "directConnection": False,
                })
                if not any(x in mongo_url.lower() for x in ["mongodb+srv://", "ssl=", "tls="]):
                    client_kwargs["tls"] = True
            
            from motor.motor_asyncio import AsyncIOMotorClient
            loop._relayd_client = AsyncIOMotorClient(mongo_url, **client_kwargs)
            loop._relayd_db = loop._relayd_client[db_name]
            return loop._relayd_db
        except RuntimeError:
            pass
        except Exception as e:
            logging.getLogger("relayd").warning(f"Failed to lazy init loop db: {e}")
        return _global_db

    @db.setter
    def db(self, val):
        global _global_db
        _global_db = val

sys.modules[__name__].__class__ = RelaydModule

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _global_db, client
    
    # Initialize Mongo
    mongo_url = os.environ["MONGO_URL"].strip()
    db_name = os.environ.get("DB_NAME", "relayd_db")
    
    # Only use TLS if the URL suggests it (Atlas) or if specifically requested
    use_tls = any(x in mongo_url.lower() for x in ["mongodb+srv://", "tls=true", "ssl=true"])
    
    # Connection options for stability (especially on Windows/Atlas)
    client_kwargs = {
        "connectTimeoutMS": 30000,
        "serverSelectionTimeoutMS": 30000,
        "heartbeatFrequencyMS": 10000,
        "maxIdleTimeMS": 60000,
        "retryWrites": True,
    }

    if use_tls:
        client_kwargs.update({
            "tlsCAFile": certifi.where(),
            "directConnection": False,
        })
        # Only add tls=True if not already in the SRV or URL params
        if not any(x in mongo_url.lower() for x in ["mongodb+srv://", "ssl=", "tls="]):
            client_kwargs["tls"] = True

    client = AsyncIOMotorClient(mongo_url, **client_kwargs)
    _global_db = client[db_name]
    
    # Store on main loop
    try:
        loop = asyncio.get_running_loop()
        loop._relayd_db = _global_db
    except Exception:
        pass

    try:
        retries = 3
        connected = False
        while retries > 0:
            try:
                await client.admin.command('ping')
                logger.info("Successfully connected to MongoDB")
                connected = True
                break
            except Exception as e:
                retries -= 1
                logger.warning(f"Database connection attempt failed ({3-retries}/3): {e}")
                if retries > 0:
                    await asyncio.sleep(2)
                else:
                    logger.error("Could not connect to database after 3 attempts.")

        if connected:
            # Indexes
            await db.users.create_index("email", unique=True)
            await db.domains.create_index([("user_id", 1), ("name", 1)], unique=True)
            await db.mailboxes.create_index("address", unique=True)
            await db.aliases.create_index("address", unique=True)
            await db.relays.create_index([("user_id", 1), ("name", 1)])
            await db.delivery_logs.create_index([("user_id", 1), ("created_at", -1)])
            await db.login_attempts.create_index("identifier")
            await db.api_tokens.create_index("token", unique=True)
            await db.api_tokens.create_index([("user_id", 1)])

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
from routers import auth_routes, domains, mail_routes, relay_routes, deliverability_routes, inbound_routes, token_routes, tags_routes, debug_routes, internal_routes

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
