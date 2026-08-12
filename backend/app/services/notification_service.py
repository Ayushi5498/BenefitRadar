"""
Notification service — writes a lightweight alert when a benefit match is found.

Called at the end of ingestion.py after a claim draft is created.
Keeps notifications decoupled from the detection pipeline.
"""
from datetime import datetime, timezone

from app.database import get_db
from app.models.match import BenefitType


_BENEFIT_DISPLAY = {
    BenefitType.PURCHASE_PROTECTION.value: "Purchase Protection",
    BenefitType.RETURN_PROTECTION.value: "Return Protection",
    BenefitType.TRAVEL_DELAY.value: "Travel Delay Insurance",
}


def _build_message(
    merchant_name: str,
    amount_usd: float,
    benefit_type: str,
) -> str:
    label = _BENEFIT_DISPLAY.get(benefit_type, benefit_type.replace("_", " ").title())
    return (
        f"Your ${amount_usd:,.2f} purchase at {merchant_name} "
        f"may be covered under {label}."
    )


async def create_notification(
    card_id: str,
    card_member_id: str,
    match_id: str,
    claim_id: str,
    merchant_name: str,
    amount_usd: float,
    benefit_type: str,
) -> dict:
    db = get_db()
    doc = {
        "card_id": card_id,
        "card_member_id": card_member_id,
        "match_id": match_id,
        "claim_id": claim_id,
        "message": _build_message(merchant_name, amount_usd, benefit_type),
        "read": False,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    result = await db.notifications.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc
