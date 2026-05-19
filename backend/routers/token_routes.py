import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from database import get_db
from models import ApiToken

router = APIRouter(prefix="/tokens", tags=["tokens"])


class TokenCreate(BaseModel):
    name: str


@router.get("")
async def list_tokens(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApiToken).where(ApiToken.user_id == user["id"]).order_by(ApiToken.created_at.desc())
    )
    tokens = result.scalars().all()
    return [
        {"id": t.id, "name": t.name, "user_id": t.user_id,
         "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
         "created_at": t.created_at.isoformat() if t.created_at else None}
        for t in tokens
    ]


@router.post("")
async def create_token(payload: TokenCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    raw_token = f"re_{secrets.token_urlsafe(32)}"
    token = ApiToken(
        id=str(uuid.uuid4()),
        user_id=user["id"],
        name=payload.name,
        token=raw_token,
        created_at=datetime.now(timezone.utc),
    )
    db.add(token)
    await db.flush()
    return {
        "id": token.id, "name": token.name, "token": raw_token,
        "user_id": token.user_id, "created_at": token.created_at.isoformat(),
    }


@router.delete("/{token_id}")
async def revoke_token(token_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user["id"]))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(t)
    return {"ok": True}
