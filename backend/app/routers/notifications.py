from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from app.database import get_db
from app.models.common import mongo_doc_to_dict
from app.models.notification import NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    summary="List notifications — unread first",
    response_model=NotificationListResponse,
)
async def list_notifications(
    card_id: Optional[str] = Query(default=None),
    card_member_id: Optional[str] = Query(default=None),
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
):
    db = get_db()
    query: dict = {}
    if card_id:
        query["card_id"] = card_id
    if card_member_id:
        query["card_member_id"] = card_member_id
    if unread_only:
        query["read"] = False

    total = await db.notifications.count_documents(query)
    unread_count = await db.notifications.count_documents({**query, "read": False})

    # Unread first, then by newest
    cursor = (
        db.notifications.find(query)
        .sort([("read", 1), ("created_at", -1)])
        .skip(skip)
        .limit(limit)
    )
    docs = [mongo_doc_to_dict(d) async for d in cursor]
    return NotificationListResponse(
        notifications=docs,
        total=total,
        unread_count=unread_count,
    )


@router.post(
    "/{notification_id}/read",
    summary="Mark a notification as read",
)
async def mark_read(notification_id: str):
    db = get_db()
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID")

    doc = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
    )
    return {"notification_id": notification_id, "read": True}


@router.post(
    "/read-all",
    summary="Mark all notifications as read for a card",
)
async def mark_all_read(
    card_id: Optional[str] = Query(default=None),
    card_member_id: Optional[str] = Query(default=None),
):
    db = get_db()
    query: dict = {"read": False}
    if card_id:
        query["card_id"] = card_id
    if card_member_id:
        query["card_member_id"] = card_member_id

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Update all matching docs
    docs = [d async for d in db.notifications.find(query)]
    for doc in docs:
        await db.notifications.update_one(
            {"_id": doc["_id"]},
            {"$set": {"read": True, "read_at": now}},
        )
    return {"marked_read": len(docs)}
