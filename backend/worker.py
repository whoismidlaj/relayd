import asyncio
import os
import logging
import signal
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from services.relay_service import send_email

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("relayd-worker")

# Shared state
db = None
client = None
is_running = True

async def process_task(task):
    """Execute a single task based on its type."""
    ttype = task.get("type")
    payload = task.get("payload", {})
    
    try:
        if ttype == "send_email":
            # For send_email, we need the provider and message details
            provider = payload.get("provider")
            msg = payload.get("message")
            result = await send_email(
                provider, 
                from_email=msg["from_email"], 
                to=msg["to"], 
                subject=msg["subject"],
                html=msg.get("html"),
                text=msg.get("text")
            )
            return result
        
        # Add more task types here (e.g., dns_check)
        logger.warning(f"Unknown task type: {ttype}")
        return {"ok": False, "error": f"Unknown task type: {ttype}"}
    
    except Exception as e:
        logger.error(f"Error executing task {task['id']}: {e}")
        return {"ok": False, "error": str(e)}

async def run_worker():
    global db, client, is_running
    
    # Initialize DB
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "relayd_db")
    
    # Same stability logic as server.py
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
        
    client = AsyncIOMotorClient(mongo_url, **client_kwargs)
    db = client[db_name]
    
    logger.info(f"Worker started. Polling queue in {db_name}...")
    
    while is_running:
        try:
            # Find a task that is pending and due for execution
            now = datetime.now(timezone.utc).isoformat()
            task = await db.tasks.find_one_and_update(
                {
                    "status": {"$in": ["pending", "retrying"]},
                    "next_run": {"$lte": now}
                },
                {"$set": {"status": "processing", "updated_at": now}},
                sort=[("priority", 1), ("created_at", 1)]
            )
            
            if not task:
                await asyncio.sleep(2) # Wait if no tasks
                continue
            
            logger.info(f"Processing task {task['id']} (Type: {task['type']})")
            
            # Execute
            result = await process_task(task)
            
            # Handle result
            now = datetime.now(timezone.utc).isoformat()
            if result.get("ok"):
                await db.tasks.update_one(
                    {"id": task["id"]},
                    {"$set": {"status": "completed", "result": result, "updated_at": now}}
                )
                logger.info(f"Task {task['id']} completed successfully")
            else:
                attempts = task.get("attempts", 0) + 1
                max_retries = task.get("max_retries", 3)
                
                if attempts < max_retries:
                    # Retry with exponential backoff (e.g., 5 min, 15 min, 30 min)
                    delay_min = 5 * (attempts ** 2)
                    next_run = (datetime.now(timezone.utc) + timedelta(minutes=delay_min)).isoformat()
                    
                    await db.tasks.update_one(
                        {"id": task["id"]},
                        {"$set": {
                            "status": "retrying",
                            "attempts": attempts,
                            "next_run": next_run,
                            "last_error": result.get("error"),
                            "updated_at": now
                        }}
                    )
                    logger.warning(f"Task {task['id']} failed. Retrying in {delay_min} min. Error: {result.get('error')}")
                else:
                    # Dead-letter queue (failed permanently)
                    await db.tasks.update_one(
                        {"id": task["id"]},
                        {"$set": {
                            "status": "failed",
                            "attempts": attempts,
                            "last_error": result.get("error"),
                            "updated_at": now
                        }}
                    )
                    logger.error(f"Task {task['id']} failed permanently after {attempts} attempts. Error: {result.get('error')}")

        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(5)

def stop_worker(*args):
    global is_running
    logger.info("Gracefully stopping worker...")
    is_running = False

if __name__ == "__main__":
    # Handle signals for graceful shutdown
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    
    asyncio.run(run_worker())
