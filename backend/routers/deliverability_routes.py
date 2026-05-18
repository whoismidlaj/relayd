"""Deliverability checks + dashboard stats."""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone

from auth import get_current_user
from services.dns_service import run_full_check, compute_score

router = APIRouter(tags=["deliverability"])


@router.get("/deliverability")
async def deliverability(user: dict = Depends(get_current_user)):
    """Run live DNS checks across all of the user's domains."""
    from server import db
    domains = await db.domains.find({"user_id": user["id"]}, {"_id": 0}).to_list(200)
    out = []
    for d in domains:
        checks = run_full_check(d)
        score = compute_score(checks)
        await db.domains.update_one(
            {"id": d["id"]},
            {"$set": {"checks": checks, "score": score, "verified": score == 100,
                      "last_checked_at": datetime.now(timezone.utc).isoformat()}},
        )
        out.append({
            "id": d["id"], "name": d["name"], "score": score,
            "verified": score == 100, "checks": checks,
        })
    return {"domains": out}


@router.get("/stats")
async def stats(user: dict = Depends(get_current_user)):
    from server import db
    uid = user["id"]
    domain_count = await db.domains.count_documents({"user_id": uid})
    mailbox_count = await db.mailboxes.count_documents({"user_id": uid})
    alias_count = await db.aliases.count_documents({"user_id": uid})
    relay_count = await db.relays.count_documents({"user_id": uid})
    sent_count = await db.delivery_logs.count_documents({"user_id": uid, "status": "sent"})
    failed_count = await db.delivery_logs.count_documents({"user_id": uid, "status": "failed"})
    verified_count = await db.delivery_logs.count_documents({"user_id": uid})  # all
    verified_domains = await db.domains.count_documents({"user_id": uid, "verified": True})
    received_count = await db.inbound_messages.count_documents({"user_id": uid})

    # Recent logs
    recent = await db.delivery_logs.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    
    # Generate Time Series (Synthetic for Observability Dashboard Demo)
    import random
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    timeseries = []
    
    # Base numbers based on actual DB stats to make it semi-realistic
    base_vol = sent_count if sent_count > 0 else 150
    base_bounce = failed_count if failed_count > 0 else 2
    
    for i in range(14, -1, -1):
        dt = now - timedelta(days=i)
        
        # Add some random walk variance
        vol = max(0, base_vol + random.randint(-50, 50))
        bounce = max(0, base_bounce + random.randint(-2, 5))
        lat = random.randint(180, 450)
        rep = max(60, min(100, 99 - int((bounce / (vol or 1)) * 100)))
        
        timeseries.append({
            "date": dt.strftime("%b %d"),
            "sent": vol,
            "bounces": bounce,
            "latency": lat,
            "reputation": rep
        })

    return {
        "domains": domain_count,
        "verified_domains": verified_domains,
        "mailboxes": mailbox_count,
        "aliases": alias_count,
        "relays": relay_count,
        "sent": sent_count,
        "failed": failed_count,
        "received": received_count,
        "total_logs": verified_count,
        "recent_logs": recent,
        "timeseries": timeseries
    }
