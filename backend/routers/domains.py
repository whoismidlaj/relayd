"""Domain CRUD + DNS record generation + live verification."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import Domain, Mailbox, Alias
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


def _shape(d: Domain) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "user_id": d.user_id,
        "dkim_selector": d.dkim_selector or "mail",
        "mail_host": d.mail_host or "mail",
        "dkim_public_key": d.dkim_public_key,
        "verified": d.verified,
        "last_checked_at": d.last_checked_at.isoformat() if d.last_checked_at else None,
        "score": d.score or 0,
        "checks": d.checks or {},
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("")
async def list_domains(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.user_id == user["id"]))
    return [_shape(d) for d in result.scalars().all()]


@router.post("")
async def create_domain(payload: DomainIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    name = payload.name.lower().strip().lstrip("@")
    if not name or "." not in name:
        raise HTTPException(status_code=400, detail="Invalid domain name")

    result = await db.execute(select(Domain).where(Domain.user_id == user["id"], Domain.name == name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Domain already exists")

    priv, pub = generate_dkim_keypair()
    domain = Domain(
        id=str(uuid.uuid4()),
        user_id=user["id"],
        name=name,
        dkim_selector=payload.dkim_selector,
        mail_host=payload.mail_host,
        dkim_private_key=priv,
        dkim_public_key=pub,
        verified=False,
        score=0,
        checks={},
        created_at=datetime.now(timezone.utc),
    )
    db.add(domain)
    await db.flush()
    return _shape(domain)


@router.get("/{domain_id}")
async def get_domain(domain_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.id == domain_id, Domain.user_id == user["id"]))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    return _shape(d)


@router.patch("/{domain_id}")
async def update_domain(domain_id: str, payload: DomainUpdate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.id == domain_id, Domain.user_id == user["id"]))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")

    changes = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Nothing to update")
    for k, v in changes.items():
        setattr(d, k, v)
    await db.flush()
    return _shape(d)


@router.delete("/{domain_id}")
async def delete_domain(domain_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.id == domain_id, Domain.user_id == user["id"]))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    await db.delete(d)  # cascades to mailboxes + aliases
    return {"ok": True}


@router.get("/{domain_id}/dns")
async def dns_records(domain_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.id == domain_id, Domain.user_id == user["id"]))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")
    records = generate_dns_records(d.name, d.dkim_selector, d.dkim_public_key, d.mail_host or "mail")
    return {"records": records, "domain": d.name, "selector": d.dkim_selector}


@router.post("/{domain_id}/verify")
async def verify_domain(domain_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.id == domain_id, Domain.user_id == user["id"]))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")

    d_dict = {"name": d.name, "dkim_selector": d.dkim_selector, "dkim_public_key": d.dkim_public_key,
              "dkim_private_key": d.dkim_private_key, "mail_host": d.mail_host}
    checks = run_full_check(d_dict)
    score = compute_score(checks)
    d.checks = checks
    d.score = score
    d.verified = score == 100
    d.last_checked_at = datetime.now(timezone.utc)
    await db.flush()
    return {"checks": checks, "score": score, "verified": d.verified}


class CloudflareSyncIn(BaseModel):
    api_token: str


@router.post("/{domain_id}/cloudflare-sync")
async def sync_cloudflare(domain_id: str, payload: CloudflareSyncIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import httpx
    result = await db.execute(select(Domain).where(Domain.id == domain_id, Domain.user_id == user["id"]))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Domain not found")

    records = generate_dns_records(d.name, d.dkim_selector, d.dkim_public_key, d.mail_host or "mail")
    headers = {"Authorization": f"Bearer {payload.api_token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.cloudflare.com/client/v4/zones?name={d.name}", headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid Cloudflare API token or domain not found.")
        zones = r.json().get("result", [])
        if not zones:
            raise HTTPException(status_code=404, detail="Zone not found in your Cloudflare account.")
        zone_id = zones[0]["id"]

        results = []
        for rec in records:
            cf_rec = {"type": rec["kind"], "name": rec["name"], "content": rec["value"], "ttl": 1}
            if rec["kind"] == "MX":
                parts = rec["value"].split(" ", 1)
                if len(parts) == 2:
                    cf_rec["priority"] = int(parts[0])
                    cf_rec["content"] = parts[1]
                else:
                    cf_rec["priority"] = 10
            resp = await client.post(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records", headers=headers, json=cf_rec)
            results.append({"record": rec["kind"], "success": resp.status_code == 200, "detail": resp.json()})

    return {"ok": True, "results": results}
