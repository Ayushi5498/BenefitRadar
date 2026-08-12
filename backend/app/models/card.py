"""Card and CardProduct schemas."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Benefit entitlement types (matches PDF benefit table)
# ---------------------------------------------------------------------------

class PurchaseProtectionEntitlement(BaseModel):
    enabled: bool = True
    coverage_cap_usd: float = 1000.0
    coverage_window_days: int = 120  # 90–120 days per PDF


class ReturnProtectionEntitlement(BaseModel):
    enabled: bool = True
    coverage_cap_usd: float = 300.0
    # Card extends the store's return window by this many extra days
    extra_days: int = 90


class TravelDelayEntitlement(BaseModel):
    enabled: bool = True
    coverage_cap_usd: float = 500.0
    # Delay must exceed this many hours to qualify
    min_delay_hours: int = 6
    # Member must file within this many days of the delay
    filing_window_days: int = 60


class BenefitEntitlements(BaseModel):
    purchase_protection: PurchaseProtectionEntitlement = Field(
        default_factory=PurchaseProtectionEntitlement
    )
    return_protection: ReturnProtectionEntitlement = Field(
        default_factory=ReturnProtectionEntitlement
    )
    travel_delay: TravelDelayEntitlement = Field(
        default_factory=TravelDelayEntitlement
    )


# ---------------------------------------------------------------------------
# CardProduct
# ---------------------------------------------------------------------------

class CardProductBase(BaseModel):
    name: str
    network: str = "American Express"
    entitlements: BenefitEntitlements = Field(default_factory=BenefitEntitlements)


class CardProductCreate(CardProductBase):
    pass


class CardProduct(CardProductBase):
    id: str


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

class CardBase(BaseModel):
    card_member_id: str
    card_product_id: str
    last_four: str
    cardholder_name: str


class CardCreate(CardBase):
    pass


class Card(CardBase):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class CardEntitlementsResponse(BaseModel):
    card_id: str
    cardholder_name: str
    card_product_name: str
    entitlements: BenefitEntitlements
