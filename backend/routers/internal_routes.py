"""Internal Dovecot integration endpoints.
These are NOT user-facing. They are called by the Dovecot container only.
Protected by a shared INTERNAL_SECRET env var instead of JWT.
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Request
from auth import verify_password

router = APIRouter(tags=["internal"])
logger = logging.getLogger("relayd")

INTERNAL_SECRET = os.environ.get("INTERNAL_SECRET", "relayd-internal")


def _check_secret(request: Request):
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/internal/dovecot-passwd", response_class=__import__("fastapi").responses.PlainTextResponse)
async def dovecot_passwd(request: Request):
    """
    Returns a Dovecot passwd-file formatted list of all active mailboxes.
    Format: email:{plain}password:::::
    Called by the Dovecot entrypoint every 5 minutes to sync credentials.
    """
    _check_secret(request)
    from server import db
    mailboxes = await db.mailboxes.find({"active": True}, {"_id": 0, "address": 1, "password_hash": 1}).to_list(None)
    lines = []
    for m in mailboxes:
        addr = m.get("address", "")
        pw_hash = m.get("password_hash", "")
        # Dovecot passwd-file format: user:{SHA512-CRYPT}hash:uid:gid:extra:::
        # We store bcrypt hashes — Dovecot supports {BLF-CRYPT} (bcrypt) natively
        lines.append(f"{addr}:{{{pw_hash.split('$')[1].upper() if pw_hash.startswith('$') else 'PLAIN'}}}{pw_hash}:::::")
    
    logger.info(f"Dovecot passwd sync: {len(lines)} mailboxes")
    return "\n".join(lines)


@router.post("/internal/dovecot-auth")
async def dovecot_auth(request: Request):
    """
    HTTP passdb endpoint for Dovecot checkpassword.
    Body: { "username": "...", "password": "..." }
    Returns 200 on success, 403 on failure.
    Used as an alternative to passwd-file for real-time auth.
    """
    _check_secret(request)
    from server import db
    body = await request.json()
    username = (body.get("username") or "").lower().strip()
    password = body.get("password") or ""

    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing credentials")

    mailbox = await db.mailboxes.find_one({"address": username, "active": True})
    if not mailbox:
        raise HTTPException(status_code=403, detail="User not found")

    if not verify_password(password, mailbox["password_hash"]):
        raise HTTPException(status_code=403, detail="Invalid password")

    return {
        "ok": True,
        "username": username,
        "uid": 5000,
        "gid": 5000,
        "home": f"/var/mail/{username}",
    }
