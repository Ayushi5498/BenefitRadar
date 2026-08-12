"""DetectedMatch schemas — output of the detection + matching engine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BenefitType(str, Enum):
    PURCHASE_PROTECTION = "purchase_protection"
    RETURN_PROTECTION = "return_protection"
    TRAVEL_DELAY = "travel_delay"


class MatchStatus(str, Enum):
    DETECTED = "detected"        # engine found a match, not yet actioned
    CLAIM_DRAFTED = "claim_drafted"  # pre-fill service created a claim draft
    DISMISSED = "dismissed"      # member or reviewer dismissed it


class MatchReason(BaseModel):
    """Human-readable explanation for why a match was flagged.

    The PDF explicitly says 'we always explain why — no black box'.
    """
    benefit_type: BenefitType
    trigger: str           # e.g. "Eligible merchant category: electronics"
    coverage_window: str   # e.g. "Valid for 120 days from purchase date"
    confidence_score: float = Field(ge=0.0, le=1.0)


class DetectedMatch(BaseModel):
    id: str
    transaction_id: str
    card_id: str
    card_member_id: str
    benefit_type: BenefitType
    confidence_score: float = Field(ge=0.0, le=1.0)
    reason: MatchReason
    status: MatchStatus = MatchStatus.DETECTED
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class MatchListResponse(BaseModel):
    matches: list[DetectedMatch]
    total: int
