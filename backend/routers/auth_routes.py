"""Auth routes: register / login / me / logout / refresh."""
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Response, Request, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    set_auth_cookies, clear_auth_cookies,
    get_current_user,
)
from database import get_db
from models import User, Mailbox, LoginAttempt

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _user_out(user: User | dict) -> dict:
    if isinstance(user, dict):
        return {
            "id": user.get("id"),
            "email": user.get("email"),
            "name": user.get("name", ""),
            "role": user.get("role", "user"),
            "created_at": user.get("created_at"),
        }
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name or "",
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/register")
async def register(payload: RegisterIn, response: Response, db: AsyncSession = Depends(get_db)):
    import os
    if os.environ.get("DISABLE_REGISTRATION", "false").lower() == "true":
        raise HTTPException(status_code=403, detail="Registration is disabled")

    email = payload.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name or email.split("@")[0],
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()  # get the id before commit

    access = create_access_token(user.id, email)
    refresh = create_refresh_token(user.id)
    set_auth_cookies(response, access, refresh)
    return _user_out(user)


@router.post("/login")
async def login(payload: LoginIn, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"

    # Rate limit check
    result = await db.execute(select(LoginAttempt).where(LoginAttempt.identifier == identifier))
    attempt = result.scalar_one_or_none()
    if attempt and attempt.count >= 5 and attempt.locked_until:
        locked_until = attempt.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    # Try user login first
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    is_mailbox = False
    mailbox_obj = None

    if not user:
        result = await db.execute(select(Mailbox).where(Mailbox.address == email))
        mailbox_obj = result.scalar_one_or_none()
        if mailbox_obj:
            is_mailbox = True

    # Verify password
    pw_hash = user.password_hash if user else (mailbox_obj.password_hash if mailbox_obj else None)
    if not pw_hash or not verify_password(payload.password, pw_hash):
        new_count = (attempt.count if attempt else 0) + 1
        if attempt:
            attempt.count = new_count
            attempt.updated_at = datetime.now(timezone.utc)
            if new_count >= 5:
                attempt.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        else:
            la = LoginAttempt(
                identifier=identifier,
                count=new_count,
                locked_until=datetime.now(timezone.utc) + timedelta(minutes=15) if new_count >= 5 else None,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(la)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Success — clear rate limit
    if attempt:
        await db.delete(attempt)

    if is_mailbox and mailbox_obj:
        uid = mailbox_obj.id
        role = "mailbox"
        access = create_access_token(uid, email, role)
        refresh = create_refresh_token(uid)
        set_auth_cookies(response, access, refresh)
        return {"id": uid, "email": email, "name": mailbox_obj.display_name or email, "role": role, "created_at": None}

    uid = user.id
    role = user.role
    access = create_access_token(uid, email, role)
    refresh = create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return _user_out(user)


@router.post("/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    import jwt
    from auth import get_jwt_secret, JWT_ALGORITHM, create_access_token, ACCESS_TOKEN_MINUTES

    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(rt, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        result = await db.execute(select(User).where(User.id == payload["sub"]))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        access = create_access_token(user.id, user.email)
        response.set_cookie(
            key="access_token", value=access, httponly=True, secure=False,
            samesite="lax", max_age=ACCESS_TOKEN_MINUTES * 60, path="/",
        )
        return {"ok": True}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


class ImapAuthIn(BaseModel):
    username: str
    password: str


@router.post("/imap")
async def imap_auth(payload: ImapAuthIn, db: AsyncSession = Depends(get_db)):
    """HTTP Auth bridge for Dovecot."""
    username = payload.username.lower().strip()

    result = await db.execute(
        select(Mailbox).where(Mailbox.address == username, Mailbox.active == True)
    )
    mailbox = result.scalar_one_or_none()
    if mailbox and verify_password(payload.password, mailbox.password_hash):
        return {"status": "ok", "user": username, "role": "mailbox"}

    result = await db.execute(select(User).where(User.email == username))
    admin = result.scalar_one_or_none()
    if admin and verify_password(payload.password, admin.password_hash):
        return {"status": "ok", "user": username, "role": admin.role}

    raise HTTPException(status_code=401, detail="Invalid credentials")
