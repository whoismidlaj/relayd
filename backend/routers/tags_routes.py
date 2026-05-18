from fastapi import APIRouter, Depends
from typing import List
from auth import get_current_user

router = APIRouter(tags=["tags"])

@router.get("/tags", response_model=List[str])
async def get_all_tags(user: dict = Depends(get_current_user)):
    import server
    """Get all unique tags used across the user's resources."""
    tags = set(["transactional", "marketing", "welcome", "system", "mailbox"])
    
    # 1. Relays (match_tags)
    relays = await server.db.relays.find({"user_id": user["id"], "match_tags": {"$exists": True}}).to_list(None)
    for r in relays:
        if isinstance(r.get("match_tags"), list):
            tags.update(r["match_tags"])
            
    # Add other resources here if they get tags in the future
    
    return sorted(list(tags))
