"""Mailboxes & Aliases routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from auth import get_current_user, hash_password

router = APIRouter(tags=["mailboxes-aliases"])


# ---------- Mailboxes ----------
class MailboxIn(BaseModel):
    local_part: str
    domain_id: str
    password: str
    display_name: Optional[str] = None
    quota_mb: int = 1024


class MailboxUpdate(BaseModel):
    password: Optional[str] = None
    display_name: Optional[str] = None
    quota_mb: Optional[int] = None
    active: Optional[bool] = None


@router.get("/mailboxes")
async def list_mailboxes(user: dict = Depends(get_current_user)):
    from server import db
    items = await db.mailboxes.find({"user_id": user["id"]}, {"_id": 0, "password_hash": 0}).to_list(500)
    return items


@router.post("/mailboxes")
async def create_mailbox(payload: MailboxIn, user: dict = Depends(get_current_user)):
    from server import db
    domain = await db.domains.find_one({"id": payload.domain_id, "user_id": user["id"]}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    local = payload.local_part.lower().strip()
    address = f"{local}@{domain['name']}"
    if await db.mailboxes.find_one({"address": address}):
        raise HTTPException(status_code=400, detail="Mailbox already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "domain_id": payload.domain_id,
        "domain": domain["name"],
        "local_part": local,
        "address": address,
        "display_name": payload.display_name or local,
        "password_hash": hash_password(payload.password),
        "quota_mb": payload.quota_mb,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.mailboxes.insert_one(doc)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return doc


@router.patch("/mailboxes/{mailbox_id}")
async def update_mailbox(mailbox_id: str, payload: MailboxUpdate, user: dict = Depends(get_current_user)):
    from server import db
    update: dict = {}
    if payload.password:
        update["password_hash"] = hash_password(payload.password)
    if payload.display_name is not None:
        update["display_name"] = payload.display_name
    if payload.quota_mb is not None:
        update["quota_mb"] = payload.quota_mb
    if payload.active is not None:
        update["active"] = payload.active
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = await db.mailboxes.update_one({"id": mailbox_id, "user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    item = await db.mailboxes.find_one({"id": mailbox_id}, {"_id": 0, "password_hash": 0})
    return item


@router.delete("/mailboxes/{mailbox_id}")
async def delete_mailbox(mailbox_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.mailboxes.delete_one({"id": mailbox_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return {"ok": True}


# ---------- Aliases ----------
class AliasIn(BaseModel):
    local_part: str  # use "*" for catch-all
    domain_id: str
    destinations: list[str]
    enabled: bool = True


class AliasUpdate(BaseModel):
    destinations: Optional[list[str]] = None
    enabled: Optional[bool] = None


@router.get("/aliases")
async def list_aliases(user: dict = Depends(get_current_user)):
    from server import db
    items = await db.aliases.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)
    return items


@router.post("/aliases")
async def create_alias(payload: AliasIn, user: dict = Depends(get_current_user)):
    from server import db
    domain = await db.domains.find_one({"id": payload.domain_id, "user_id": user["id"]}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    if not payload.destinations:
        raise HTTPException(status_code=400, detail="At least one destination required")
    local = payload.local_part.strip()
    address = f"{local}@{domain['name']}"
    if await db.aliases.find_one({"address": address}):
        raise HTTPException(status_code=400, detail="Alias already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "domain_id": payload.domain_id,
        "domain": domain["name"],
        "local_part": local,
        "address": address,
        "catch_all": local == "*",
        "destinations": [d.strip().lower() for d in payload.destinations if d.strip()],
        "enabled": payload.enabled,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.aliases.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/aliases/{alias_id}")
async def update_alias(alias_id: str, payload: AliasUpdate, user: dict = Depends(get_current_user)):
    from server import db
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = await db.aliases.update_one({"id": alias_id, "user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alias not found")
    return await db.aliases.find_one({"id": alias_id}, {"_id": 0})


@router.delete("/aliases/{alias_id}")
async def delete_alias(alias_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.aliases.delete_one({"id": alias_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alias not found")
    return {"ok": True}
