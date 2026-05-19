from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from auth import get_current_user
from database import get_db
from models import Relay

router = APIRouter(tags=["tags"])

@router.get("/tags", response_model=List[str])
async def get_all_tags(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get all unique tags used across the user's resources."""
    tags = set(["transactional", "marketing", "welcome", "system", "mailbox"])
    
    # 1. Relays (match_tags)
    result = await db.execute(select(Relay.match_tags).where(Relay.user_id == user["id"]))
    rows = result.scalars().all()
    for match_tags in rows:
        if isinstance(match_tags, list):
            tags.update(match_tags)
            
    return sorted(list(tags))
