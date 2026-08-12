"""Claim schemas — pre-filled drafts and their lifecycle."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ClaimStatus(str, Enum):
    """Mirrors the status shown in the PDF's 'track it' screen."""
    DETECTED = "detected"          # draft exists, not yet submitted by member
    SUBMITTED = "submitted"        # member tapped Submit
    UNDER_REVIEW = "under_review"  # bank is reviewing
    APPROVED = "approved"
    REJECTED = "rejected"


class ClaimBase(BaseModel):
    """Fields that are auto-populated by the claim pre-fill service."""
    match_id: str
    transaction_id: str
    card_id: str
    card_member_id: str

    # Pre-filled fields (what the PDF calls "auto-drafted")
    merchant_name: str
    amount_usd: float
    purchased_at: datetime
    benefit_type: str        # human-readable label for the UI
    benefit_description: str # plain-English reason, e.g. "Purchase Protection"
    coverage_cap_usd: float

    # Optional supporting info
    travel_booking_ref: Optional[str] = None
    store_refused_return: bool = False


class Claim(ClaimBase):
    id: str
    status: ClaimStatus = ClaimStatus.DETECTED
    edited: bool = False   # True if member changed any pre-filled field before submitting
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    # Final payout amount (set on approval)
    payout_amount_usd: Optional[float] = None
    # Reviewer notes (for rejected claims)
    reviewer_notes: Optional[str] = None


class ClaimSubmitRequest(BaseModel):
    """Payload for POST /claims/{id}/submit."""
    edited: bool = False   # True if the user changed any pre-filled field before submitting


class ClaimSubmitResponse(BaseModel):
    claim_id: str
    status: ClaimStatus
    message: str


class ClaimApproveRequest(BaseModel):
    approved: bool = True
    reviewer_notes: Optional[str] = None


class ClaimListResponse(BaseModel):
    claims: list[Claim]
    total: int
