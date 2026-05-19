"""Debug export endpoint — sanitized system state snapshot for bug reporting."""
import os
import platform
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import Relay, Domain, Mailbox, Alias, DeliveryLog, Task

router = APIRouter(tags=["debug"])


def _redact(val: str | None, keep: int = 4) -> str:
    """Mask a secret, keeping only the last `keep` chars."""
    if not val:
        return ""
    s = str(val)
    if len(s) <= keep:
        return "***"
    return f"{'*' * (len(s) - keep)}{s[-keep:]}"


def _sanitize_relay(r: Relay) -> dict:
    cfg = dict(r.config or {})
    # Redact all known secret fields
    for secret_key in ("api_key", "password", "secret_access_key", "token"):
        if secret_key in cfg:
            cfg[secret_key] = _redact(cfg.get(secret_key))
    return {
        "id": r.id,
        "name": r.name,
        "type": r.type,
        "priority": r.priority,
        "weight": r.weight,
        "is_default": r.is_default,
        "daily_quota": r.daily_quota,
        "health_status": r.health_status,
        "match_domains": r.match_domains or [],
        "match_tags": r.match_tags or [],
        "usage_today": r.usage_today,
        "config_keys": list(cfg.keys()),  # which fields are set, but not values
        "config": cfg,
    }


def _sanitize_domain(d: Domain) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "verified": d.verified,
        "score": d.score,
        "last_checked_at": d.last_checked_at.isoformat() if d.last_checked_at else None,
        "checks": d.checks or {},
        "dkim_selector": d.dkim_selector,
    }


def _sanitize_mailbox(m: Mailbox) -> dict:
    return {
        "id": m.id,
        "address": m.address,
        "domain": m.domain,
        "display_name": m.display_name,
        "active": m.active,
        "quota_mb": m.quota_mb,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _sanitize_alias(a: Alias) -> dict:
    return {
        "id": a.id,
        "address": a.address,
        "domain": a.domain,
        "catch_all": a.catch_all,
        "destinations": a.destinations or [],
        "enabled": a.enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/debug/export")
async def debug_export(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Export a sanitized JSON snapshot of the current app state for bug reporting."""
    uid = user["id"]

    relays_res = await db.execute(select(Relay).where(Relay.user_id == uid))
    relays = relays_res.scalars().all()

    domains_res = await db.execute(select(Domain).where(Domain.user_id == uid))
    domains = domains_res.scalars().all()

    mailboxes_res = await db.execute(select(Mailbox).where(Mailbox.user_id == uid))
    mailboxes = mailboxes_res.scalars().all()

    aliases_res = await db.execute(select(Alias).where(Alias.user_id == uid))
    aliases = aliases_res.scalars().all()

    sent_count = (await db.execute(
        select(func.count(DeliveryLog.id)).where(DeliveryLog.user_id == uid, DeliveryLog.status == "sent")
    )).scalar()

    failed_count = (await db.execute(
        select(func.count(DeliveryLog.id)).where(DeliveryLog.user_id == uid, DeliveryLog.status == "failed")
    )).scalar()

    pending_count = (await db.execute(
        select(func.count(Task.id)).where(Task.user_id == uid, Task.type == "send_email", Task.status == "pending")
    )).scalar()

    # received_count is 0 since we removed direct mongo writes and store everything inside Dovecot Maildirs
    received_count = 0

    recent_logs_res = await db.execute(
        select(DeliveryLog)
        .where(DeliveryLog.user_id == uid)
        .order_by(DeliveryLog.created_at.desc())
        .limit(10)
    )
    recent_logs = recent_logs_res.scalars().all()

    recent_logs_sanitized = []
    for l in recent_logs:
        recent_logs_sanitized.append({
            "id": l.id,
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
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "relayd_version": "0.1.0",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "disable_registration": os.environ.get("DISABLE_REGISTRATION", "false"),
            "has_frontend_url": bool(os.environ.get("FRONTEND_URL")),
            "has_jwt_secret_custom": os.environ.get("JWT_SECRET", "").lower() not in (
                "", "change-me-in-production-please-set-a-long-random-string"
            ),
            "admin_email": os.environ.get("ADMIN_EMAIL", ""),
        },
        "counts": {
            "domains": len(domains),
            "mailboxes": len(mailboxes),
            "aliases": len(aliases),
            "relays": len(relays),
            "sent": sent_count,
            "failed": failed_count,
            "received": received_count,
            "pending_queue": pending_count,
        },
        "relays": [_sanitize_relay(r) for r in relays],
        "domains": [_sanitize_domain(d) for d in domains],
        "mailboxes": [_sanitize_mailbox(m) for m in mailboxes],
        "aliases": [_sanitize_alias(a) for a in aliases],
        "recent_delivery_logs": recent_logs_sanitized,
    }
