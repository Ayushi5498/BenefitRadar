"""
Stage 2 — Benefit Matching Engine.

Implements the 'Detection & Matching Engine' box from the PDF architecture
(Slide 4) and the benefit-matching rules table (Slide 6).

Architecture note
-----------------
The `MatchScorer` abstract base class defines the interface that a real
ML model would implement.  `RuleBasedScorer` is the prototype
implementation that uses deterministic rules + weighted scoring.
Swapping in a scikit-learn or TensorFlow model later means only
replacing the scorer — the pipeline around it stays the same.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models.card import BenefitEntitlements
from app.models.match import BenefitType, MatchReason
from app.models.transaction import MerchantCategory, TransactionBase


# ---------------------------------------------------------------------------
# Categories that are eligible for purchase / return protection
# (per typical Amex benefit terms — extensible)
# ---------------------------------------------------------------------------
_PURCHASE_PROTECTION_CATEGORIES: set[MerchantCategory] = {
    MerchantCategory.ELECTRONICS,
    MerchantCategory.CLOTHING,
    MerchantCategory.SPORTING_GOODS,
    MerchantCategory.JEWELRY,
    MerchantCategory.HOME_APPLIANCES,
    MerchantCategory.OTHER,
}

_RETURN_PROTECTION_CATEGORIES: set[MerchantCategory] = {
    MerchantCategory.ELECTRONICS,
    MerchantCategory.CLOTHING,
    MerchantCategory.SPORTING_GOODS,
    MerchantCategory.JEWELRY,
    MerchantCategory.HOME_APPLIANCES,
    MerchantCategory.OTHER,
}


# ---------------------------------------------------------------------------
# Scorer interface
# ---------------------------------------------------------------------------

@dataclass
class ScoredMatch:
    benefit_type: BenefitType
    confidence_score: float          # 0.0 – 1.0
    trigger_description: str
    coverage_window_description: str
    qualifies: bool


class MatchScorer(abc.ABC):
    """
    Abstract scorer — the seam where an ML model would plug in.

    A concrete implementation receives a transaction and the card's
    entitlements and returns the *best* benefit match (or None).
    """

    @abc.abstractmethod
    def score(
        self,
        txn: TransactionBase,
        entitlements: BenefitEntitlements,
        as_of: Optional[datetime] = None,
    ) -> Optional[ScoredMatch]:
        """Return the highest-confidence qualifying match, or None."""
        ...


# ---------------------------------------------------------------------------
# Rule-based scorer (prototype implementation)
# ---------------------------------------------------------------------------

class RuleBasedScorer(MatchScorer):
    """
    Determines benefit type using the trigger rules from PDF Slide 6.

    Priority order (matches PDF — each purchase is matched to exactly one):
      1. Travel-Delay Insurance  (most time-sensitive — checked first)
      2. Return Protection
      3. Purchase Protection

    Confidence is a weighted sum of signal strength rather than a
    black-box model, keeping results fully explainable (PDF Slide 8).
    """

    def score(
        self,
        txn: TransactionBase,
        entitlements: BenefitEntitlements,
        as_of: Optional[datetime] = None,
    ) -> Optional[ScoredMatch]:
        as_of = as_of or datetime.now(timezone.utc).replace(tzinfo=None)

        # Try each benefit in priority order
        result = (
            self._try_travel_delay(txn, entitlements, as_of)
            or self._try_return_protection(txn, entitlements, as_of)
            or self._try_purchase_protection(txn, entitlements, as_of)
        )
        return result

    # ------------------------------------------------------------------
    # Individual benefit checks
    # ------------------------------------------------------------------

    def _try_travel_delay(
        self,
        txn: TransactionBase,
        entitlements: BenefitEntitlements,
        as_of: datetime,
    ) -> Optional[ScoredMatch]:
        ent = entitlements.travel_delay
        if not ent.enabled:
            return None
        if txn.merchant_category != MerchantCategory.AIRLINE:
            return None
        if not txn.travel_booking_ref:
            return None

        delay_mins = txn.flight_delay_minutes or 0
        min_delay_mins = ent.min_delay_hours * 60

        if delay_mins < min_delay_mins:
            return None

        # Coverage window: from the delay until the filing deadline
        filing_deadline = txn.purchased_at + timedelta(days=ent.filing_window_days)
        if as_of > filing_deadline:
            return None

        # Confidence: how much the delay exceeds the threshold
        # Maxes out at 2× the threshold → confidence 1.0
        ratio = min(delay_mins / min_delay_mins, 2.0) / 2.0
        confidence = 0.6 + (0.4 * ratio)  # floor at 0.60 once threshold met

        days_remaining = (filing_deadline - as_of).days

        return ScoredMatch(
            benefit_type=BenefitType.TRAVEL_DELAY,
            confidence_score=round(confidence, 3),
            trigger_description=(
                f"Flight delay of {delay_mins} min exceeds the "
                f"{ent.min_delay_hours}-hour threshold on booking "
                f"'{txn.travel_booking_ref}'."
            ),
            coverage_window_description=(
                f"Claim must be filed within {ent.filing_window_days} days of "
                f"the delay ({days_remaining} days remaining)."
            ),
            qualifies=True,
        )

    def _try_return_protection(
        self,
        txn: TransactionBase,
        entitlements: BenefitEntitlements,
        as_of: datetime,
    ) -> Optional[ScoredMatch]:
        ent = entitlements.return_protection
        if not ent.enabled:
            return None
        if txn.merchant_category not in _RETURN_PROTECTION_CATEGORIES:
            return None
        if not txn.store_refused_return:
            # No signal yet that the store refused — can't match
            return None

        # Coverage: store's window (assumed 30 days) + card's extra days
        store_window_days = 30
        total_window = store_window_days + ent.extra_days
        coverage_expires = txn.purchased_at + timedelta(days=total_window)
        if as_of > coverage_expires:
            return None

        days_remaining = (coverage_expires - as_of).days
        # High confidence because store_refused_return is an explicit signal
        confidence = 0.88

        return ScoredMatch(
            benefit_type=BenefitType.RETURN_PROTECTION,
            confidence_score=confidence,
            trigger_description=(
                f"Store refused return of eligible purchase from "
                f"'{txn.merchant_name}'."
            ),
            coverage_window_description=(
                f"Return protection is valid for the store's {store_window_days}-day "
                f"window plus your card's extra {ent.extra_days} days "
                f"({days_remaining} days remaining)."
            ),
            qualifies=True,
        )

    def _try_purchase_protection(
        self,
        txn: TransactionBase,
        entitlements: BenefitEntitlements,
        as_of: datetime,
    ) -> Optional[ScoredMatch]:
        ent = entitlements.purchase_protection
        if not ent.enabled:
            return None
        if txn.merchant_category not in _PURCHASE_PROTECTION_CATEGORIES:
            return None

        # Coverage window: 90–120 days (we use the product's configured value)
        coverage_expires = txn.purchased_at + timedelta(days=ent.coverage_window_days)
        if as_of > coverage_expires:
            return None

        days_remaining = (coverage_expires - as_of).days

        # Confidence based on how recently the item was purchased
        # (fresher = higher confidence — less chance the window expired)
        days_elapsed = (as_of - txn.purchased_at).days
        freshness_score = max(0.0, 1.0 - (days_elapsed / ent.coverage_window_days))
        confidence = 0.55 + (0.35 * freshness_score)

        return ScoredMatch(
            benefit_type=BenefitType.PURCHASE_PROTECTION,
            confidence_score=round(confidence, 3),
            trigger_description=(
                f"Eligible purchase from '{txn.merchant_name}' in category "
                f"'{txn.merchant_category.value}' (${txn.amount_usd:.2f})."
            ),
            coverage_window_description=(
                f"Purchase protection covers up to {ent.coverage_window_days} days "
                f"from purchase date ({days_remaining} days remaining)."
            ),
            qualifies=True,
        )


# ---------------------------------------------------------------------------
# Module-level singleton — swap this for an ML scorer in production
# ---------------------------------------------------------------------------
default_scorer: MatchScorer = RuleBasedScorer()
