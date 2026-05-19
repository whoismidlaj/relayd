"""Relay providers + test email send + delivery logs."""
import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import Relay, DeliveryLog, Domain, Task
from services.relay_service import send_email

router = APIRouter(tags=["relays"])

PROVIDER_TYPES = ("smtp", "resend", "ses", "brevo", "smtp2go", "direct")


def _relay_out(r: Relay) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "name": r.name,
        "type": r.type,
        "config": r.config or {},
        "priority": r.priority,
        "is_default": r.is_default,
        "enabled": r.enabled,
        "daily_quota": r.daily_quota,
        "weight": r.weight,
        "usage_today": r.usage_today,
        "usage_date": r.usage_date,
        "health_status": r.health_status,
        "match_domains": r.match_domains or [],
        "match_tags": r.match_tags or [],
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _log_out(l: DeliveryLog) -> dict:
    return {
        "id": l.id,
        "user_id": l.user_id,
        "from_email": l.from_email,
        "to": l.to_email,
        "subject": l.subject,
        "status": l.status,
        "provider_id": l.provider_id,
        "provider_name": l.provider_name,
        "provider_type": l.provider_type,
        "message_id": l.message_id,
        "error": l.error,
        "attempts": l.attempts or [],
        "created_at": l.created_at.isoformat() if l.created_at else None,
    }


def _scrub_secrets(p: dict) -> dict:
    cfg = dict(p.get("config", {}) or {})
    for k in ("password", "api_key", "secret_access_key"):
        if k in cfg and cfg[k]:
            cfg[k] = "••••••••" + str(cfg[k])[-4:]
    return {**p, "config": cfg}


@router.get("/relays/tasks")
async def list_tasks(user: dict = Depends(get_current_user), status: Optional[str] = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    q = select(Task).where(Task.user_id == user["id"]).order_by(Task.created_at.desc()).limit(limit)
    if status:
        q = q.where(Task.status == status)
    result = await db.execute(q)
    tasks = result.scalars().all()
    return [
        {"id": t.id, "type": t.type, "status": t.status, "priority": t.priority,
         "attempts": t.attempts, "created_at": t.created_at.isoformat() if t.created_at else None,
         "updated_at": t.updated_at.isoformat() if t.updated_at else None,
         "last_error": t.last_error}
        for t in tasks
    ]


@router.get("/relays/tasks/stats")
async def task_stats(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    uid = user["id"]
    pending = (await db.execute(select(func.count(Task.id)).where(Task.user_id == uid, Task.status.in_(["pending", "retrying"])))).scalar()
    failed  = (await db.execute(select(func.count(Task.id)).where(Task.user_id == uid, Task.status == "failed"))).scalar()
    completed = (await db.execute(select(func.count(Task.id)).where(Task.user_id == uid, Task.status == "completed"))).scalar()
    return {"pending": pending, "failed": failed, "completed": completed}


class RelayIn(BaseModel):
    name: str
    type: Literal["smtp", "resend", "ses", "brevo", "smtp2go", "direct"]
    config: dict
    priority: int = 100
    is_default: bool = False
    daily_quota: int = 0
    weight: int = 100
    match_domains: list[str] = []
    match_tags: list[str] = []


class RelayUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    priority: Optional[int] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None
    daily_quota: Optional[int] = None
    weight: Optional[int] = None
    match_domains: Optional[list[str]] = None
    match_tags: Optional[list[str]] = None


@router.get("/relays")
async def list_relays(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Relay).where(Relay.user_id == user["id"]).order_by(Relay.priority.asc()))
    relays = result.scalars().all()
    out = []
    for r in relays:
        rid = r.id
        total_sends = (await db.execute(select(func.count(DeliveryLog.id)).where(DeliveryLog.user_id == user["id"], DeliveryLog.provider_id == rid))).scalar()
        successful_sends = (await db.execute(select(func.count(DeliveryLog.id)).where(DeliveryLog.user_id == user["id"], DeliveryLog.provider_id == rid, DeliveryLog.status == "sent"))).scalar()
        d = _relay_out(r)
        d["total_sends"] = total_sends
        d["successful_sends"] = successful_sends
        out.append(_scrub_secrets(d))
    return out


@router.post("/relays")
async def create_relay(payload: RelayIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.is_default:
        await db.execute(update(Relay).where(Relay.user_id == user["id"]).values(is_default=False))

    relay = Relay(
        id=str(uuid.uuid4()),
        user_id=user["id"],
        name=payload.name,
        type=payload.type,
        config=payload.config,
        priority=payload.priority,
        is_default=payload.is_default,
        enabled=True,
        daily_quota=payload.daily_quota,
        weight=payload.weight,
        usage_today=0,
        usage_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        health_status="healthy",
        match_domains=payload.match_domains,
        match_tags=payload.match_tags,
        created_at=datetime.now(timezone.utc),
    )
    db.add(relay)
    await db.flush()
    return _scrub_secrets(_relay_out(relay))


@router.patch("/relays/{relay_id}")
async def update_relay(relay_id: str, payload: RelayUpdate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Relay).where(Relay.id == relay_id, Relay.user_id == user["id"]))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Relay not found")

    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to update")
    if changes.get("is_default"):
        await db.execute(update(Relay).where(Relay.user_id == user["id"]).values(is_default=False))
    for k, v in changes.items():
        setattr(r, k, v)
    await db.flush()
    return _scrub_secrets(_relay_out(r))


@router.delete("/relays/{relay_id}")
async def delete_relay(relay_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Relay).where(Relay.id == relay_id, Relay.user_id == user["id"]))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Relay not found")
    await db.delete(r)
    return {"ok": True}


# ---------- Test email send with retry/failover ----------
class TestEmailIn(BaseModel):
    from_email: EmailStr
    to: EmailStr
    subject: str
    body: str
    relay_id: Optional[str] = None
    use_failover: bool = True
    tags: list[str] = []


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
async def send_test_email(payload: TestEmailIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.relay_id:
        result = await db.execute(select(Relay).where(Relay.id == payload.relay_id, Relay.user_id == user["id"]))
        relay = result.scalar_one_or_none()
        if not relay:
            raise HTTPException(status_code=404, detail="Relay not found")
        providers = [_relay_out(relay)]
    else:
        result = await db.execute(select(Relay).where(Relay.user_id == user["id"], Relay.enabled == True).order_by(Relay.priority.asc()))
        all_relays = [_relay_out(r) for r in result.scalars().all()]
        if not all_relays:
            raise HTTPException(status_code=400, detail="No configured relays found")

        recipient_domain = payload.to.split("@")[-1].lower()

        def score_relay(r):
            score = r.get("priority", 100)
            domains = r.get("match_domains", [])
            if recipient_domain in domains:
                score -= 1000
            elif any(recipient_domain.endswith(d.lstrip("*.")) for d in domains if d.startswith("*.")):
                score -= 1000
            tags = r.get("match_tags", [])
            for t in payload.tags:
                if t in tags:
                    score -= 500
            if r.get("is_default"):
                score -= 10
            return score

        import itertools, random
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for r in all_relays:
            r["_computed_score"] = score_relay(r)
            r["_weight"] = r.get("weight", 100)
            if r.get("usage_date") != today_str:
                r["usage_today"] = 0

        all_relays.sort(key=lambda x: x["_computed_score"])

        providers = []
        for score, group in itertools.groupby(all_relays, key=lambda x: x["_computed_score"]):
            group_list = list(group)
            for r in group_list:
                quota = r.get("daily_quota", 0)
                usage = r.get("usage_today", 0)
                if quota > 0:
                    pct = usage / quota
                    if pct >= 1.0:
                        r["_weight"] = 0
                    elif pct > 0.90:
                        r["_weight"] = int(r["_weight"] * 0.1)
                    elif pct > 0.75:
                        r["_weight"] = int(r["_weight"] * 0.5)
            while group_list:
                total_weight = sum(r["_weight"] for r in group_list)
                if total_weight <= 0:
                    chosen = random.choice(group_list)
                else:
                    rand_val = random.uniform(0, total_weight)
                    upto = 0
                    for r in group_list:
                        if upto + r["_weight"] >= rand_val:
                            chosen = r
                            break
                        upto += r["_weight"]
                providers.append(chosen)
                group_list.remove(chosen)

        if not payload.use_failover and providers:
            providers = [providers[0]]

    final_result = None
    used_provider = None
    attempts: list[dict] = []
    max_retries = 2

    for prov in providers:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_quota = prov.get("daily_quota", 0)
        usage_today = prov.get("usage_today", 0)
        if prov.get("usage_date") != today_str:
            usage_today = 0

        if daily_quota > 0 and usage_today >= daily_quota:
            attempts.append({"provider_id": prov.get("id"), "provider_name": prov.get("name"), "type": prov.get("type"),
                             "attempt": 1, "ok": False, "error": "Daily quota exceeded", "message_id": None})
            continue

        for attempt_n in range(1, max_retries + 1):
            if prov.get("type") == "direct" or prov.get("id") == "virtual-direct":
                from_domain = payload.from_email.split("@")[-1]
                result = await db.execute(select(Domain).where(Domain.user_id == user["id"], Domain.name == from_domain))
                domain_doc = result.scalar_one_or_none()
                if domain_doc:
                    prov["config"] = {"dkim_private_key": domain_doc.dkim_private_key, "dkim_selector": domain_doc.dkim_selector or "mail"}

            result = await _attempt_send(prov, payload)
            attempts.append({"provider_id": prov.get("id"), "provider_name": prov.get("name"), "type": prov.get("type"),
                             "attempt": attempt_n, "ok": result["ok"], "error": result.get("error"), "message_id": result.get("message_id")})

            if result["ok"]:
                final_result = result
                used_provider = prov
                # Update usage/health
                await db.execute(
                    update(Relay)
                    .where(Relay.id == prov["id"])
                    .values(usage_date=today_str, health_status="healthy", usage_today=Relay.usage_today + 1)
                )
                break
            else:
                err_msg = str(result.get("error", "")).lower()
                new_health = "error"
                if "429" in err_msg or "rate limit" in err_msg or "quota" in err_msg:
                    new_health = "rate_limited"
                elif "bounce" in err_msg:
                    new_health = "high_bounce_rate"
                await db.execute(update(Relay).where(Relay.id == prov["id"]).values(health_status=new_health))

            if attempt_n < max_retries:
                await asyncio.sleep(0.5)
        if final_result and final_result.get("ok"):
            break

    # Final fallback: direct send
    if not final_result or not final_result.get("ok"):
        if payload.use_failover:
            from_domain = payload.from_email.split("@")[-1]
            result = await db.execute(select(Domain).where(Domain.user_id == user["id"], Domain.name == from_domain))
            domain_doc = result.scalar_one_or_none()
            virtual_direct = {
                "id": "virtual-direct",
                "name": "System Fallback (Direct MX)",
                "type": "direct",
                "config": {
                    "dkim_private_key": domain_doc.dkim_private_key if domain_doc else None,
                    "dkim_selector": domain_doc.dkim_selector or "mail" if domain_doc else "mail",
                },
            }
            result = await _attempt_send(virtual_direct, payload)
            attempts.append({"provider_id": "virtual-direct", "provider_name": "System Fallback (Direct MX)",
                             "type": "direct", "attempt": 1, "ok": result["ok"],
                             "error": result.get("error"), "message_id": result.get("message_id")})
            if result["ok"]:
                final_result = result
                used_provider = virtual_direct

    status = "sent" if (final_result and final_result.get("ok")) else "failed"
    log = DeliveryLog(
        id=str(uuid.uuid4()),
        user_id=user["id"],
        from_email=payload.from_email,
        to_email=payload.to,
        subject=payload.subject,
        status=status,
        provider_id=used_provider["id"] if used_provider else None,
        provider_name=used_provider["name"] if used_provider else None,
        provider_type=used_provider["type"] if used_provider else None,
        message_id=final_result.get("message_id") if final_result else None,
        error=None if status == "sent" else (attempts[-1]["error"] if attempts else "no providers"),
        attempts=attempts,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()
    return _log_out(log)


@router.get("/logs")
async def list_logs(user: dict = Depends(get_current_user), limit: int = 100, db: AsyncSession = Depends(get_db)):
    if user.get("role") == "mailbox":
        q = select(DeliveryLog).where(DeliveryLog.from_email == user["email"])
    else:
        q = select(DeliveryLog).where(DeliveryLog.user_id == user["id"])
    result = await db.execute(q.order_by(DeliveryLog.created_at.desc()).limit(limit))
    return [_log_out(l) for l in result.scalars().all()]


@router.delete("/logs/{log_id}")
async def delete_log(log_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeliveryLog).where(DeliveryLog.id == log_id, DeliveryLog.user_id == user["id"]))
    l = result.scalar_one_or_none()
    if l:
        await db.delete(l)
    return {"ok": True}


@router.post("/logs/{log_id}/retry")
async def retry_log(log_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeliveryLog).where(DeliveryLog.id == log_id, DeliveryLog.user_id == user["id"]))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    payload = TestEmailIn(
        from_email=log.from_email, to=log.to_email,
        subject=log.subject, body="Retry of failed delivery",
        relay_id=log.provider_id,
    )
    return await send_test_email(payload, user=user, db=db)
