"""Mailboxes & Aliases routes."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user, hash_password
from database import get_db
from models import Mailbox, Alias, Domain, Relay, Task

logger = logging.getLogger("relayd")

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


def _mb_out(m: Mailbox) -> dict:
    return {
        "id": m.id,
        "user_id": m.user_id,
        "domain_id": m.domain_id,
        "domain": m.domain,
        "local_part": m.local_part,
        "address": m.address,
        "display_name": m.display_name,
        "quota_mb": m.quota_mb,
        "active": m.active,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("/mailboxes")
async def list_mailboxes(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.user_id == user["id"]))
    return [_mb_out(m) for m in result.scalars().all()]


@router.post("/mailboxes")
async def create_mailbox(payload: MailboxIn, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.id == payload.domain_id, Domain.user_id == user["id"]))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    local = payload.local_part.lower().strip()
    address = f"{local}@{domain.name}"

    result = await db.execute(select(Mailbox).where(Mailbox.address == address))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Mailbox already exists")

    mailbox = Mailbox(
        id=str(uuid.uuid4()),
        user_id=user["id"],
        domain_id=payload.domain_id,
        domain=domain.name,
        local_part=local,
        address=address,
        display_name=payload.display_name or local,
        password_hash=hash_password(payload.password),
        quota_mb=payload.quota_mb,
        active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(mailbox)
    await db.flush()

    background_tasks.add_task(_send_welcome_email, address, payload.display_name or local, domain.name, user["id"])
    return _mb_out(mailbox)


async def _send_welcome_email(address: str, display_name: str, domain: str, user_id: str):
    """Fire-and-forget welcome email to a newly created mailbox."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(Relay).where(Relay.user_id == user_id, Relay.is_default == True))
            relay = result.scalar_one_or_none()
            if not relay:
                result = await session.execute(select(Relay).where(Relay.user_id == user_id))
                relay = result.scalars().first()
            if not relay:
                logger.info(f"No relay configured — skipping welcome email for {address}")
                return

            html_body = f"""
<div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:32px;">
  <h2>Welcome to Relayd, {display_name}!</h2>
  <p>Your mailbox <strong>{address}</strong> is ready. Connection settings:</p>
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <tr style="background:#f5f5f5;"><td style="padding:10px;font-weight:600;">Incoming (IMAP)</td><td></td></tr>
    <tr><td style="padding:8px;color:#555;">Server</td><td style="font-family:monospace;">mail.{domain}</td></tr>
    <tr style="background:#f9f9f9;"><td style="padding:8px;color:#555;">Port</td><td style="font-family:monospace;">993 (SSL/TLS)</td></tr>
    <tr><td style="padding:8px;color:#555;">Username</td><td style="font-family:monospace;">{address}</td></tr>
    <tr style="background:#f5f5f5;"><td style="padding:10px;font-weight:600;">Outgoing (SMTP)</td><td></td></tr>
    <tr><td style="padding:8px;color:#555;">Server</td><td style="font-family:monospace;">mail.{domain}</td></tr>
    <tr style="background:#f9f9f9;"><td style="padding:8px;color:#555;">Port</td><td style="font-family:monospace;">587 (STARTTLS)</td></tr>
    <tr><td style="padding:8px;color:#555;">Username</td><td style="font-family:monospace;">{address}</td></tr>
  </table>
</div>"""

            task = Task(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type="send_email",
                status="pending",
                payload={
                    "provider": {"id": relay.id, "name": relay.name, "type": relay.type, "config": relay.config},
                    "message": {
                        "from_email": f"no-reply@{domain}",
                        "to": [address],
                        "subject": "Welcome to Relayd — your mailbox is ready",
                        "html": html_body,
                        "text": f"Welcome to Relayd, {display_name}!\n\nYour mailbox {address} is ready.\n",
                    },
                },
                priority=100,
                created_at=datetime.now(timezone.utc),
            )
            session.add(task)
            await session.commit()
            logger.info(f"Queued welcome email for {address}")
        except Exception as e:
            logger.warning(f"Failed to queue welcome email for {address}: {e}")


@router.patch("/mailboxes/{mailbox_id}")
async def update_mailbox(mailbox_id: str, payload: MailboxUpdate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.id == mailbox_id, Mailbox.user_id == user["id"]))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    if payload.password:
        m.password_hash = hash_password(payload.password)
    if payload.display_name is not None:
        m.display_name = payload.display_name
    if payload.quota_mb is not None:
        m.quota_mb = payload.quota_mb
    if payload.active is not None:
        m.active = payload.active

    await db.flush()
    return _mb_out(m)


@router.delete("/mailboxes/{mailbox_id}")
async def delete_mailbox(mailbox_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Mailbox).where(Mailbox.id == mailbox_id, Mailbox.user_id == user["id"]))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    await db.delete(m)
    return {"ok": True}


# ---------- Aliases ----------
class AliasIn(BaseModel):
    local_part: str
    domain_id: str
    destinations: list[str]
    enabled: bool = True


class AliasUpdate(BaseModel):
    destinations: Optional[list[str]] = None
    enabled: Optional[bool] = None


def _alias_out(a: Alias) -> dict:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "domain_id": a.domain_id,
        "domain": a.domain,
        "local_part": a.local_part,
        "address": a.address,
        "catch_all": a.catch_all,
        "destinations": a.destinations or [],
        "enabled": a.enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/aliases")
async def list_aliases(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alias).where(Alias.user_id == user["id"]))
    return [_alias_out(a) for a in result.scalars().all()]


@router.post("/aliases")
async def create_alias(payload: AliasIn, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Domain).where(Domain.id == payload.domain_id, Domain.user_id == user["id"]))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    if not payload.destinations:
        raise HTTPException(status_code=400, detail="At least one destination required")

    local = payload.local_part.strip()
    address = f"{local}@{domain.name}"

    result = await db.execute(select(Alias).where(Alias.address == address))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Alias already exists")

    alias = Alias(
        id=str(uuid.uuid4()),
        user_id=user["id"],
        domain_id=payload.domain_id,
        domain=domain.name,
        local_part=local,
        address=address,
        catch_all=local == "*",
        destinations=[d.strip().lower() for d in payload.destinations if d.strip()],
        enabled=payload.enabled,
        created_at=datetime.now(timezone.utc),
    )
    db.add(alias)
    await db.flush()
    return _alias_out(alias)


@router.patch("/aliases/{alias_id}")
async def update_alias(alias_id: str, payload: AliasUpdate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alias).where(Alias.id == alias_id, Alias.user_id == user["id"]))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Alias not found")
    if payload.destinations is not None:
        a.destinations = payload.destinations
    if payload.enabled is not None:
        a.enabled = payload.enabled
    await db.flush()
    return _alias_out(a)


@router.delete("/aliases/{alias_id}")
async def delete_alias(alias_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alias).where(Alias.id == alias_id, Alias.user_id == user["id"]))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Alias not found")
    await db.delete(a)
    return {"ok": True}
