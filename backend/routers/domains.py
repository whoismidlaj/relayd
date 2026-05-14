"""Domain CRUD + DNS record generation + live verification."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from auth import get_current_user
from services.dns_service import (
    generate_dkim_keypair, generate_dns_records,
    run_full_check, compute_score,
)

router = APIRouter(prefix="/domains", tags=["domains"])


class DomainIn(BaseModel):
    name: str
    dkim_selector: str = "mail"
    mail_host: str = "mail"


class DomainUpdate(BaseModel):
    dkim_selector: Optional[str] = None
    mail_host: Optional[str] = None


def _shape(d: dict) -> dict:
    return {
        "id": d["id"],
        "name": d["name"],
        "user_id": d["user_id"],
        "dkim_selector": d.get("dkim_selector", "mail"),
        "mail_host": d.get("mail_host", "mail"),
        "dkim_public_key": d.get("dkim_public_key"),
        "verified": d.get("verified", False),
        "last_checked_at": d.get("last_checked_at"),
        "score": d.get("score", 0),
        "checks": d.get("checks", {}),
        "created_at": d.get("created_at"),
    }


@router.get("")
async def list_domains(user: dict = Depends(get_current_user)):
    from server import db
    items = await db.domains.find({"user_id": user["id"]}, {"_id": 0, "dkim_private_key": 0}).to_list(500)
    return items


@router.post("")
async def create_domain(payload: DomainIn, user: dict = Depends(get_current_user)):
    from server import db
    name = payload.name.lower().strip().lstrip("@")
    if not name or "." not in name:
        raise HTTPException(status_code=400, detail="Invalid domain name")
    if await db.domains.find_one({"user_id": user["id"], "name": name}):
        raise HTTPException(status_code=400, detail="Domain already exists")
    priv, pub = generate_dkim_keypair()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": name,
        "dkim_selector": payload.dkim_selector,
        "mail_host": payload.mail_host,
        "dkim_private_key": priv,
        "dkim_public_key": pub,
        "verified": False,
        "score": 0,
        "checks": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.domains.insert_one(doc)
    return _shape(doc)


@router.get("/{domain_id}")
async def get_domain(domain_id: str, user: dict = Depends(get_current_user)):
    from server import db
    d = await db.domains.find_one({"id": domain_id, "user_id": user["id"]}, {"_id": 0, "dkim_private_key": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    return d


@router.patch("/{domain_id}")
async def update_domain(domain_id: str, payload: DomainUpdate, user: dict = Depends(get_current_user)):
    from server import db
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = await db.domains.update_one({"id": domain_id, "user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Domain not found")
    d = await db.domains.find_one({"id": domain_id}, {"_id": 0, "dkim_private_key": 0})
    return d


@router.delete("/{domain_id}")
async def delete_domain(domain_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.domains.delete_one({"id": domain_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Domain not found")
    await db.mailboxes.delete_many({"domain_id": domain_id})
    await db.aliases.delete_many({"domain_id": domain_id})
    return {"ok": True}


@router.get("/{domain_id}/dns")
async def dns_records(domain_id: str, user: dict = Depends(get_current_user)):
    from server import db
    d = await db.domains.find_one({"id": domain_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    records = generate_dns_records(d["name"], d["dkim_selector"], d["dkim_public_key"], d.get("mail_host", "mail"))
    return {"records": records, "domain": d["name"], "selector": d["dkim_selector"]}


@router.post("/{domain_id}/verify")
async def verify_domain(domain_id: str, user: dict = Depends(get_current_user)):
    from server import db
    d = await db.domains.find_one({"id": domain_id, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    checks = run_full_check(d)
    score = compute_score(checks)
    verified = score == 100
    await db.domains.update_one(
        {"id": domain_id},
        {"$set": {
            "checks": checks, "score": score, "verified": verified,
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"checks": checks, "score": score, "verified": verified}
