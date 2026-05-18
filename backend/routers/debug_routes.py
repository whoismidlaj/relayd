"""Debug export endpoint — sanitized system state snapshot for bug reporting."""
import os
import platform
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from auth import get_current_user

router = APIRouter(tags=["debug"])


def _redact(val: str | None, keep: int = 4) -> str:
    """Mask a secret, keeping only the last `keep` chars."""
    if not val:
        return ""
    s = str(val)
    if len(s) <= keep:
        return "***"
    return f"{'*' * (len(s) - keep)}{s[-keep:]}"


def _sanitize_relay(r: dict) -> dict:
    cfg = dict(r.get("config") or {})
    # Redact all known secret fields
    for secret_key in ("api_key", "password", "secret_access_key", "token"):
        if secret_key in cfg:
            cfg[secret_key] = _redact(cfg.get(secret_key))
    return {
        "id": r.get("id"),
        "name": r.get("name"),
        "type": r.get("type"),
        "priority": r.get("priority"),
        "weight": r.get("weight"),
        "is_default": r.get("is_default"),
        "daily_quota": r.get("daily_quota"),
        "health_status": r.get("health_status"),
        "match_domains": r.get("match_domains", []),
        "match_tags": r.get("match_tags", []),
        "usage_today": r.get("usage_today", 0),
        "config_keys": list(cfg.keys()),  # which fields are set, but not values
        "config": cfg,
    }


def _sanitize_domain(d: dict) -> dict:
    return {
        "id": d.get("id"),
        "name": d.get("name"),
        "verified": d.get("verified"),
        "score": d.get("score"),
        "last_checked_at": d.get("last_checked_at"),
        "checks": d.get("checks", {}),
        "mx": d.get("mx"),
        "spf": d.get("spf"),
        "dkim_selector": d.get("dkim_selector"),
    }


def _sanitize_mailbox(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "address": m.get("address"),
        "domain": m.get("domain"),
        "display_name": m.get("display_name"),
        "active": m.get("active"),
        "quota_mb": m.get("quota_mb"),
        "created_at": m.get("created_at"),
    }


def _sanitize_alias(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "address": a.get("address"),
        "domain": a.get("domain"),
        "catch_all": a.get("catch_all"),
        "destinations": a.get("destinations", []),
        "enabled": a.get("enabled"),
        "created_at": a.get("created_at"),
    }


@router.get("/debug/export")
async def debug_export(user: dict = Depends(get_current_user)):
    """Export a sanitized JSON snapshot of the current app state for bug reporting."""
    from server import db
    uid = user["id"]

    relays     = await db.relays.find({"user_id": uid}, {"_id": 0}).to_list(None)
    domains    = await db.domains.find({"user_id": uid}, {"_id": 0}).to_list(None)
    mailboxes  = await db.mailboxes.find({"user_id": uid}, {"_id": 0, "password_hash": 0}).to_list(None)
    aliases    = await db.aliases.find({"user_id": uid}, {"_id": 0}).to_list(None)

    sent_count     = await db.delivery_logs.count_documents({"user_id": uid, "status": "sent"})
    failed_count   = await db.delivery_logs.count_documents({"user_id": uid, "status": "failed"})
    pending_count  = await db.send_queue.count_documents({"user_id": uid, "status": "pending"})
    received_count = await db.inbound_messages.count_documents({"user_id": uid})

    recent_logs = await db.delivery_logs.find(
        {"user_id": uid}, {"_id": 0, "html": 0, "text": 0, "body": 0}
    ).sort("created_at", -1).limit(10).to_list(10)

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
        "recent_delivery_logs": recent_logs,
    }
