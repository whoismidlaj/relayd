"""Relay providers + test email send + delivery logs."""
import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal

from auth import get_current_user
from services.relay_service import send_email

router = APIRouter(tags=["relays"])

PROVIDER_TYPES = ("smtp", "resend", "ses", "brevo", "smtp2go", "direct")

@router.get("/relays/tasks")
async def list_tasks(user: dict = Depends(get_current_user), status: Optional[str] = None, limit: int = 50):
    from server import db
    query = {"user_id": user["id"]}
    if status:
        query["status"] = status
    items = await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return items

@router.get("/relays/tasks/stats")
async def task_stats(user: dict = Depends(get_current_user)):
    from server import db
    pending = await db.tasks.count_documents({"user_id": user["id"], "status": {"$in": ["pending", "retrying"]}})
    failed = await db.tasks.count_documents({"user_id": user["id"], "status": "failed"})
    completed = await db.tasks.count_documents({"user_id": user["id"], "status": "completed"})
    return {"pending": pending, "failed": failed, "completed": completed}


class RelayIn(BaseModel):
    name: str
    type: Literal["smtp", "resend", "ses", "brevo", "smtp2go", "direct"]
    config: dict
    priority: int = 100
    is_default: bool = False


class RelayUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    priority: Optional[int] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None


def _scrub_secrets(p: dict) -> dict:
    """Mask sensitive fields when listing providers."""
    cfg = dict(p.get("config", {}) or {})
    for k in ("password", "api_key", "secret_access_key"):
        if k in cfg and cfg[k]:
            cfg[k] = "••••••••" + str(cfg[k])[-4:]
    return {**p, "config": cfg}


@router.get("/relays")
async def list_relays(user: dict = Depends(get_current_user)):
    from server import db
    items = await db.relays.find({"user_id": user["id"]}, {"_id": 0}).sort("priority", 1).to_list(100)
    return [_scrub_secrets(p) for p in items]


@router.post("/relays")
async def create_relay(payload: RelayIn, user: dict = Depends(get_current_user)):
    from server import db
    if payload.is_default:
        await db.relays.update_many({"user_id": user["id"]}, {"$set": {"is_default": False}})
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": payload.name,
        "type": payload.type,
        "config": payload.config,
        "priority": payload.priority,
        "is_default": payload.is_default,
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.relays.insert_one(doc)
    doc.pop("_id", None)
    return _scrub_secrets(doc)


@router.patch("/relays/{relay_id}")
async def update_relay(relay_id: str, payload: RelayUpdate, user: dict = Depends(get_current_user)):
    from server import db
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    if update.get("is_default"):
        await db.relays.update_many({"user_id": user["id"]}, {"$set": {"is_default": False}})
    result = await db.relays.update_one({"id": relay_id, "user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Relay not found")
    item = await db.relays.find_one({"id": relay_id}, {"_id": 0})
    return _scrub_secrets(item)


@router.delete("/relays/{relay_id}")
async def delete_relay(relay_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.relays.delete_one({"id": relay_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Relay not found")
    return {"ok": True}


# ---------- Test email send with retry/failover ----------
class TestEmailIn(BaseModel):
    from_email: EmailStr
    to: EmailStr
    subject: str
    body: str
    relay_id: Optional[str] = None
    use_failover: bool = True


async def _attempt_send(provider: dict, payload: TestEmailIn) -> dict:
    return await send_email(
        provider,
        from_email=payload.from_email,
        to=[payload.to],
        subject=payload.subject,
        html=f"<div style='font-family:sans-serif;font-size:14px;line-height:1.5'>{payload.body}</div>",
        text=payload.body,
    )


@router.post("/send/test")
async def send_test_email(payload: TestEmailIn, user: dict = Depends(get_current_user)):
    from server import db

    if payload.relay_id:
        provider = await db.relays.find_one({"id": payload.relay_id, "user_id": user["id"]}, {"_id": 0})
        if not provider:
            raise HTTPException(status_code=404, detail="Relay not found")
        providers = [provider]
    else:
        default = await db.relays.find_one({"user_id": user["id"], "is_default": True, "enabled": True}, {"_id": 0})
        if not default:
            raise HTTPException(status_code=400, detail="No default relay configured")
        providers = [default]
        if payload.use_failover:
            extras = await db.relays.find(
                {"user_id": user["id"], "enabled": True, "id": {"$ne": default["id"]}},
                {"_id": 0},
            ).sort("priority", 1).to_list(10)
            providers.extend(extras)

    final_result = None
    used_provider = None
    attempts: list[dict] = []
    max_retries = 2

    for prov in providers:
        for attempt_n in range(1, max_retries + 1):
            # If it's a direct send, we need to inject DKIM info from the domain
            if prov.get("type") == "direct" or prov.get("id") == "virtual-direct":
                from_domain = payload.from_email.split('@')[-1]
                domain_doc = await db.domains.find_one({"user_id": user["id"], "name": from_domain})
                if domain_doc:
                    prov["config"] = {
                        "dkim_private_key": domain_doc.get("dkim_private_key"),
                        "dkim_selector": domain_doc.get("dkim_selector", "mail")
                    }

            result = await _attempt_send(prov, payload)
            attempts.append({
                "provider_id": prov.get("id"), "provider_name": prov.get("name"), "type": prov.get("type"),
                "attempt": attempt_n, "ok": result["ok"],
                "error": result.get("error"), "message_id": result.get("message_id"),
            })
            if result["ok"]:
                final_result = result
                used_provider = prov
                break
            if attempt_n < max_retries:
                await asyncio.sleep(0.5)
        if final_result and final_result.get("ok"):
            break

    # FINAL FALLBACK: If everything failed, try a virtual direct send
    if not final_result or not final_result.get("ok"):
        if payload.use_failover:
            from_domain = payload.from_email.split('@')[-1]
            domain_doc = await db.domains.find_one({"user_id": user["id"], "name": from_domain})
            
            virtual_direct = {
                "id": "virtual-direct",
                "name": "System Fallback (Direct MX)",
                "type": "direct",
                "config": {
                    "dkim_private_key": domain_doc.get("dkim_private_key") if domain_doc else None,
                    "dkim_selector": domain_doc.get("dkim_selector", "mail") if domain_doc else "mail"
                }
            }
            
            result = await _attempt_send(virtual_direct, payload)
            attempts.append({
                "provider_id": "virtual-direct", "provider_name": "System Fallback (Direct MX)", "type": "direct",
                "attempt": 1, "ok": result["ok"],
                "error": result.get("error"), "message_id": result.get("message_id"),
            })
            if result["ok"]:
                final_result = result
                used_provider = virtual_direct

    status = "sent" if (final_result and final_result.get("ok")) else "failed"
    log = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "from_email": payload.from_email,
        "to": payload.to,
        "subject": payload.subject,
        "status": status,
        "provider_id": used_provider["id"] if used_provider else None,
        "provider_name": used_provider["name"] if used_provider else None,
        "provider_type": used_provider["type"] if used_provider else None,
        "message_id": final_result.get("message_id") if final_result else None,
        "error": None if status == "sent" else (attempts[-1]["error"] if attempts else "no providers"),
        "attempts": attempts,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.delivery_logs.insert_one(log)
    log.pop("_id", None)
    return log


# ---------- Delivery logs ----------
@router.get("/logs")
async def list_logs(user: dict = Depends(get_current_user), limit: int = 100):
    from server import db
    items = await db.delivery_logs.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return items


@router.delete("/logs/{log_id}")
async def delete_log(log_id: str, user: dict = Depends(get_current_user)):
    from server import db
    await db.delivery_logs.delete_one({"id": log_id, "user_id": user["id"]})
    return {"ok": True}


@router.post("/logs/{log_id}/retry")
async def retry_log(log_id: str, user: dict = Depends(get_current_user)):
    from server import db
    log = await db.delivery_logs.find_one({"id": log_id, "user_id": user["id"]}, {"_id": 0})
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    payload = TestEmailIn(
        from_email=log["from_email"], to=log["to"],
        subject=log["subject"], body="Retry of failed delivery",
        relay_id=log.get("provider_id"),
    )
    return await send_test_email(payload, user)  # type: ignore
