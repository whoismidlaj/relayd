from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user

router = APIRouter(prefix="/inbound", tags=["inbound"])

@router.get("/messages")
async def list_messages(user: dict = Depends(get_current_user), limit: int = 50):
    from server import db
    query = {"to": user["email"]} if user.get("role") == "mailbox" else {"user_id": user["id"], "is_mailbox": {"$ne": True}}
    items = await db.inbound_messages.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return items

@router.get("/messages/{message_id}")
async def get_message(message_id: str, user: dict = Depends(get_current_user)):
    from server import db
    query = {"id": message_id, "to": user["email"]} if user.get("role") == "mailbox" else {"id": message_id, "user_id": user["id"]}
    msg = await db.inbound_messages.find_one(query, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    
    await db.inbound_messages.update_one({"id": message_id}, {"$set": {"read": True}})
    return msg

@router.delete("/messages/{message_id}")
async def delete_message(message_id: str, user: dict = Depends(get_current_user)):
    from server import db
    query = {"id": message_id, "to": user["email"]} if user.get("role") == "mailbox" else {"id": message_id, "user_id": user["id"]}
    result = await db.inbound_messages.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True}

@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    from server import db
    query = {"to": user["email"]} if user.get("role") == "mailbox" else {"user_id": user["id"], "is_mailbox": {"$ne": True}}
    total = await db.inbound_messages.count_documents(query)
    unread = await db.inbound_messages.count_documents({**query, "read": False})
    return {"total": total, "unread": unread}
