"""JWT-based authentication module."""
import os
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Response, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60 * 24  # 24h for self-hosted comfort
REFRESH_TOKEN_DAYS = 7


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str = "user") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        key="access_token", value=access, httponly=True, secure=False,
        samesite="lax", max_age=ACCESS_TOKEN_MINUTES * 60, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(lambda: None),  # overridden below via middleware approach
) -> dict:
    """
    Dependency that returns the current authenticated user.
    Gets a fresh DB session internally to avoid circular dependency issues.
    """
    from database import AsyncSessionLocal
    from models import User, Mailbox, ApiToken

    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with AsyncSessionLocal() as session:
        # --- API Key auth ---
        if token.startswith("re_"):
            result = await session.execute(
                select(ApiToken).where(ApiToken.token == token)
            )
            api_key = result.scalar_one_or_none()
            if not api_key:
                raise HTTPException(status_code=401, detail="Invalid API token")

            # Update last_used_at
            await session.execute(
                update(ApiToken)
                .where(ApiToken.id == api_key.id)
                .values(last_used_at=datetime.now(timezone.utc))
            )
            await session.commit()

            result = await session.execute(select(User).where(User.id == api_key.user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}

        # --- JWT auth ---
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")

            role = payload.get("role", "user")
            user_id = payload["sub"]

            if role == "mailbox":
                result = await session.execute(
                    select(Mailbox).where(Mailbox.id == user_id)
                )
                mb = result.scalar_one_or_none()
                if not mb:
                    raise HTTPException(status_code=401, detail="Mailbox not found")
                return {"id": mb.id, "email": mb.address, "role": "mailbox"}

            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
