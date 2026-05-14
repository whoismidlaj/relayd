import uuid
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user

router = APIRouter(prefix="/tokens", tags=["tokens"])

class TokenCreate(BaseModel):
    name: str

@router.get("")
async def list_tokens(user: dict = Depends(get_current_user)):
    from server import db
    items = await db.api_tokens.find({"user_id": user["id"]}, {"_id": 0, "token": 0}).sort("created_at", -1).to_list(100)
    return items

@router.post("")
async def create_token(payload: TokenCreate, user: dict = Depends(get_current_user)):
    from server import db
    
    # Generate a secure token with 're_' prefix
    raw_token = f"re_{secrets.token_urlsafe(32)}"
    
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "name": payload.name,
        "token": raw_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used_at": None,
    }
    await db.api_tokens.insert_one(doc)
    
    # Only return the raw token once during creation
    doc.pop("_id", None)
    return doc

@router.delete("/{token_id}")
async def revoke_token(token_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.api_tokens.delete_one({"id": token_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"ok": True}
