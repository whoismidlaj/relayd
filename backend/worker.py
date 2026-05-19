"""
Background worker — polls the tasks table and executes jobs.
Uses PostgreSQL's SELECT FOR UPDATE SKIP LOCKED for safe concurrent processing.
"""
import asyncio
import os
import logging
import signal
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from services.relay_service import send_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("relayd-worker")

is_running = True


async def process_task(task, session: AsyncSession) -> dict:
    """Execute a single task based on its type."""
    ttype = task.type
    payload = task.payload or {}

    try:
        if ttype == "send_email":
            provider = payload.get("provider")
            msg = payload.get("message")
            result = await send_email(
                provider,
                from_email=msg["from_email"],
                to=msg["to"],
                subject=msg["subject"],
                html=msg.get("html"),
                text=msg.get("text"),
            )
            return result

        logger.warning(f"Unknown task type: {ttype}")
        return {"ok": False, "error": f"Unknown task type: {ttype}"}

    except Exception as e:
        logger.error(f"Error executing task {task.id}: {e}")
        return {"ok": False, "error": str(e)}


async def run_worker():
    global is_running

    from database import get_engine, AsyncSessionLocal
    from models import Task, Relay

    get_engine()  # Initialise engine from DATABASE_URL
    logger.info("Worker started. Polling tasks table...")

    while is_running:
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.now(timezone.utc)

                # Claim one pending/retrying task atomically using SKIP LOCKED
                result = await session.execute(
                    select(Task)
                    .where(
                        Task.status.in_(["pending", "retrying"]),
                        Task.next_run <= now,
                    )
                    .order_by(Task.priority.asc(), Task.created_at.asc())
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                task = result.scalar_one_or_none()

                if not task:
                    await session.rollback()
                    await asyncio.sleep(2)
                    continue

                # Mark as processing
                task.status = "processing"
                task.updated_at = now
                await session.commit()

            # Execute the task (outside transaction to avoid long-held locks)
            async with AsyncSessionLocal() as session:
                # Re-fetch after commit
                result = await session.execute(select(Task).where(Task.id == task.id))
                task = result.scalar_one_or_none()
                if not task:
                    continue

                logger.info(f"Processing task {task.id} (type={task.type})")
                exec_result = await process_task(task, session)

                now = datetime.now(timezone.utc)
                if exec_result.get("ok"):
                    task.status = "completed"
                    task.result = exec_result
                    task.updated_at = now
                    await session.commit()
                    logger.info(f"Task {task.id} completed successfully")

                    # Increment relay usage counter
                    if task.type == "send_email":
                        provider = task.payload.get("provider", {})
                        prov_id = provider.get("id")
                        if prov_id:
                            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                            await session.execute(
                                update(Relay)
                                .where(Relay.id == prov_id)
                                .values(
                                    usage_date=today_str,
                                    health_status="healthy",
                                    usage_today=Relay.usage_today + 1,
                                )
                            )
                            await session.commit()
                else:
                    attempts = (task.attempts or 0) + 1
                    max_retries = task.max_retries or 3

                    if attempts < max_retries:
                        delay_min = 5 * (attempts ** 2)
                        next_run = datetime.now(timezone.utc) + timedelta(minutes=delay_min)
                        task.status = "retrying"
                        task.attempts = attempts
                        task.next_run = next_run
                        task.last_error = exec_result.get("error")
                        task.updated_at = now
                        await session.commit()
                        logger.warning(f"Task {task.id} failed. Retrying in {delay_min} min.")
                    else:
                        task.status = "failed"
                        task.attempts = attempts
                        task.last_error = exec_result.get("error")
                        task.updated_at = now
                        await session.commit()
                        logger.error(f"Task {task.id} permanently failed after {attempts} attempts.")

        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(5)


def stop_worker(*args):
    global is_running
    logger.info("Gracefully stopping worker...")
    is_running = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    asyncio.run(run_worker())
