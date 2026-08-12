"""Notification schemas — lightweight 'we noticed it' alerts."""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Notification(BaseModel):
    id: str
    card_id: str
    card_member_id: str
    match_id: str
    claim_id: str
    message: str           # plain-English, e.g. "Your $249 purchase at TechMart may be covered"
    read: bool = False
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


class NotificationListResponse(BaseModel):
    notifications: list[Notification]
    total: int
    unread_count: int
