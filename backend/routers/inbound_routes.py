from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user

router = APIRouter(prefix="/inbound", tags=["inbound"])

@router.get("/messages")
async def list_messages(user: dict = Depends(get_current_user), limit: int = 50):
    from server import db
    items = await db.inbound_messages.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return items

@router.get("/messages/{message_id}")
async def get_message(message_id: str, user: dict = Depends(get_current_user)):
    from server import db
    msg = await db.inbound_messages.find_one({"id": message_id, "user_id": user["id"]}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Mark as read
    await db.inbound_messages.update_one({"id": message_id}, {"$set": {"read": True}})
    return msg

@router.delete("/messages/{message_id}")
async def delete_message(message_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.inbound_messages.delete_one({"id": message_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True}

@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    from server import db
    total = await db.inbound_messages.count_documents({"user_id": user["id"]})
    unread = await db.inbound_messages.count_documents({"user_id": user["id"], "read": False})
    return {"total": total, "unread": unread}
