"""
Stage 1 — Rules-based candidate filter.

This is the "cheap first check" from the PDF (Slide 5).
It runs on every single transaction and quickly rules out the obvious
no's before the more expensive matching/scoring step.

Rejection criteria:
- Merchant category is categorically ineligible for ALL benefits
- Amount is below the minimum worth processing
- Cash advances and certain excluded categories are always rejected

Only transactions that PASS this filter proceed to the MatchScorer.
"""
from app.models.transaction import MerchantCategory, TransactionBase
from app.models.card import BenefitEntitlements


# Categories that are never eligible for any card benefit
_ALWAYS_EXCLUDED: set[MerchantCategory] = {
    MerchantCategory.RESTAURANT,
    MerchantCategory.GROCERY,
    MerchantCategory.GAS_STATION,
    MerchantCategory.CASH_ADVANCE,
}

# Minimum transaction amount (USD) to bother checking
_MIN_AMOUNT_USD: float = 25.0


class FilterResult:
    __slots__ = ("passed", "reason")

    def __init__(self, passed: bool, reason: str):
        self.passed = passed
        self.reason = reason

    def __bool__(self):
        return self.passed


def run_rules_filter(
    txn: TransactionBase,
    entitlements: BenefitEntitlements,
) -> FilterResult:
    """
    Returns a FilterResult indicating whether the transaction should
    proceed to the matching engine.

    This is deliberately cheap: no DB calls, no ML inference.
    """
    # 1. Always-excluded categories
    if txn.merchant_category in _ALWAYS_EXCLUDED:
        return FilterResult(
            False,
            f"Merchant category '{txn.merchant_category.value}' is not "
            "eligible for any card benefit.",
        )

    # 2. Amount floor
    if txn.amount_usd < _MIN_AMOUNT_USD:
        return FilterResult(
            False,
            f"Transaction amount ${txn.amount_usd:.2f} is below the minimum "
            f"threshold of ${_MIN_AMOUNT_USD:.2f}.",
        )

    # 3. Does the card have *any* benefit enabled at all?
    e = entitlements
    has_any = (
        e.purchase_protection.enabled
        or e.return_protection.enabled
        or e.travel_delay.enabled
    )
    if not has_any:
        return FilterResult(False, "Card product has no active benefit entitlements.")

    # 4. Travel-delay: category must be airline, and delay signal must be present
    #    (if only travel_delay is enabled and neither of the other two apply,
    #     we'd catch this below — but we can skip here if no airline txn)
    is_airline = txn.merchant_category == MerchantCategory.AIRLINE
    has_delay = (txn.flight_delay_minutes or 0) > 0
    travel_only = (
        not e.purchase_protection.enabled
        and not e.return_protection.enabled
        and e.travel_delay.enabled
    )
    if travel_only and (not is_airline or not has_delay):
        return FilterResult(
            False,
            "Only travel-delay benefit is active, but transaction is not an "
            "airline purchase with a recorded delay.",
        )

    return FilterResult(True, "Passed all rules checks — proceeding to matching.")
