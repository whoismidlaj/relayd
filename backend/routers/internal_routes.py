"""Internal Dovecot integration endpoints.
These are NOT user-facing. They are called by the Dovecot container only.
Protected by a shared INTERNAL_SECRET env var instead of JWT.
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import verify_password
from database import get_db
from models import Mailbox

router = APIRouter(tags=["internal"])
logger = logging.getLogger("relayd")

INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "relayd-internal")


def _check_secret(request: Request):
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/internal/dovecot-passwd", response_class=__import__("fastapi").responses.PlainTextResponse)
async def dovecot_passwd(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Returns a Dovecot passwd-file formatted list of all active mailboxes.
    Format: email:{plain}password:::::
    Called by the Dovecot entrypoint every 5 minutes to sync credentials.
    """
    _check_secret(request)
    
    result = await db.execute(select(Mailbox).where(Mailbox.active == True))
    mailboxes = result.scalars().all()
    lines = []
    for m in mailboxes:
        addr = m.address
        pw_hash = m.password_hash
        if not addr or not pw_hash:
            continue
        # Map Python bcrypt hash ($2b$...) to Dovecot's BLF-CRYPT scheme.
        if pw_hash.startswith(("$2b$", "$2a$", "$2y$")):
            dovecot_entry = f"{addr}:{{BLF-CRYPT}}{pw_hash}:::::"
        elif pw_hash.startswith("$5$"):
            dovecot_entry = f"{addr}:{{SHA256-CRYPT}}{pw_hash}:::::"
        elif pw_hash.startswith("$6$"):
            dovecot_entry = f"{addr}:{{SHA512-CRYPT}}{pw_hash}:::::"
        else:
            # Fallback: store as plain (not recommended but won't crash Dovecot)
            dovecot_entry = f"{addr}:{{PLAIN}}{pw_hash}:::::"
        lines.append(dovecot_entry)
    
    logger.info(f"Dovecot passwd sync: {len(lines)} mailboxes")
    return "\n".join(lines)


@router.post("/internal/dovecot-auth")
async def dovecot_auth(request: Request, db: AsyncSession = Depends(get_db)):
    """
    HTTP passdb endpoint for Dovecot checkpassword.
    Body: { "username": "...", "password": "..." }
    Returns 200 on success, 403 on failure.
    Used as an alternative to passwd-file for real-time auth.
    """
    _check_secret(request)
    body = await request.json()
    username = (body.get("username") or "").lower().strip()
    password = body.get("password") or ""

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing credentials")

    result = await db.execute(select(Mailbox).where(Mailbox.address == username, Mailbox.active == True))
    mailbox = result.scalar_one_or_none()
    if not mailbox:
        raise HTTPException(status_code=403, detail="User not found")

    if not verify_password(password, mailbox.password_hash):
        raise HTTPException(status_code=403, detail="Invalid password")

    return {
        "ok": True,
        "username": username,
        "uid": 5000,
        "gid": 5000,
        "home": f"/var/mail/{username}",
    }
