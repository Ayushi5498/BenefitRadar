"""
Stage 3 — Claim Pre-Fill Service.

Takes a confirmed match and auto-generates a fully pre-populated claim
document.  The card member only needs to review and tap Submit.

Matches the 'Claim Pre-Fill Service / Auto-drafts claim' box in the
PDF's system architecture diagram (Slide 4).
"""
from datetime import datetime

from app.models.card import BenefitEntitlements
from app.models.claim import ClaimBase
from app.models.match import BenefitType, DetectedMatch
from app.models.transaction import Transaction

_BENEFIT_LABELS = {
    BenefitType.PURCHASE_PROTECTION: "Purchase Protection",
    BenefitType.RETURN_PROTECTION: "Return Protection",
    BenefitType.TRAVEL_DELAY: "Travel Delay Insurance",
}

_BENEFIT_DESCRIPTIONS = {
    BenefitType.PURCHASE_PROTECTION: (
        "Your card covers this purchase against damage or theft for up to "
        "the coverage cap."
    ),
    BenefitType.RETURN_PROTECTION: (
        "Your card allows you to return this item even though the store "
        "refused the return, up to the coverage cap."
    ),
    BenefitType.TRAVEL_DELAY: (
        "Your flight was delayed beyond the covered threshold. Your card "
        "covers eligible out-of-pocket expenses."
    ),
}


def build_claim_draft(
    match: DetectedMatch,
    txn: Transaction,
    entitlements: BenefitEntitlements,
) -> ClaimBase:
    """
    Construct a pre-filled ClaimBase from a confirmed match.

    All fields are populated automatically — the member only confirms.
    """
    benefit_type_enum = BenefitType(match.benefit_type)

    # Determine the coverage cap from the card's entitlements
    if benefit_type_enum == BenefitType.PURCHASE_PROTECTION:
        cap = entitlements.purchase_protection.coverage_cap_usd
    elif benefit_type_enum == BenefitType.RETURN_PROTECTION:
        cap = entitlements.return_protection.coverage_cap_usd
    else:
        cap = entitlements.travel_delay.coverage_cap_usd

    return ClaimBase(
        match_id=match.id,
        transaction_id=txn.id,
        card_id=txn.card_id,
        card_member_id=txn.card_member_id,
        merchant_name=txn.merchant_name,
        amount_usd=min(txn.amount_usd, cap),  # cap at the entitlement limit
        purchased_at=txn.purchased_at,
        benefit_type=_BENEFIT_LABELS[benefit_type_enum],
        benefit_description=_BENEFIT_DESCRIPTIONS[benefit_type_enum],
        coverage_cap_usd=cap,
        travel_booking_ref=txn.travel_booking_ref,
        store_refused_return=txn.store_refused_return,
    )
