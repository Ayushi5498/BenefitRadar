"""
Ingestion service — orchestrates the full detection pipeline.

Flow (matching PDF Slide 7 — 'Your Journey, Step by Step'):
  1. Transaction event arrives
  2. Look up card + card product entitlements
  3. Run rules filter (cheap, synchronous)
  4. Run match scorer (structured, deterministic for prototype)
  5. If match found → persist DetectedMatch + call claim pre-fill
  6. Persist Claim draft
  7. Return result

This service is called by the /transactions/simulate endpoint and
could equally be called by a Kafka/Pub-Sub consumer in production.
"""
import random
import string
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from bson import ObjectId

from app.database import get_db
from app.models.card import BenefitEntitlements, CardProductBase
from app.models.claim import Claim, ClaimStatus
from app.models.common import mongo_doc_to_dict
from app.models.match import BenefitType, DetectedMatch, MatchReason, MatchStatus
from app.models.transaction import (
    MerchantCategory,
    Transaction,
    TransactionBase,
    TransactionSimulateRequest,
    TransactionStatus,
)
from app.services.claim_prefill import build_claim_draft
from app.services.matcher import default_scorer
from app.services.notification_service import create_notification
from app.services.rules_filter import run_rules_filter


# ---------------------------------------------------------------------------
# Simulated merchant catalogue for random transaction generation
# ---------------------------------------------------------------------------
_MOCK_MERCHANTS = [
    ("TechMart", MerchantCategory.ELECTRONICS, 249.99),
    ("SoundWave Audio", MerchantCategory.ELECTRONICS, 399.00),
    ("FashionForward", MerchantCategory.CLOTHING, 89.95),
    ("RunnersPro", MerchantCategory.SPORTING_GOODS, 159.00),
    ("DiamondLux Jewellers", MerchantCategory.JEWELRY, 620.00),
    ("HomeComfort", MerchantCategory.HOME_APPLIANCES, 549.00),
    ("SkyJet Airlines", MerchantCategory.AIRLINE, 480.00),
    ("GlobalAir", MerchantCategory.AIRLINE, 310.00),
    ("QuickBite", MerchantCategory.RESTAURANT, 32.00),
    ("FreshGrocer", MerchantCategory.GROCERY, 75.00),
]


def _random_ref(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


async def simulate_transaction(
    req: TransactionSimulateRequest,
) -> dict:
    """
    Main entry point for POST /transactions/simulate.

    If no card_id is provided, picks the first available card in the DB.
    If no merchant details are provided, picks a random mock merchant.
    Returns a dict with the transaction and detection outcome.
    """
    db = get_db()

    # ------------------------------------------------------------------
    # 1. Resolve card + entitlements
    # ------------------------------------------------------------------
    card_doc = None
    if req.card_id:
        card_doc = await db.cards.find_one({"_id": ObjectId(req.card_id)})
    if card_doc is None:
        card_doc = await db.cards.find_one({})
    if card_doc is None:
        raise ValueError(
            "No cards found in the database. Run the seed script first: "
            "python -m app.seed"
        )

    card_id = str(card_doc["_id"])
    card_member_id = card_doc["card_member_id"]

    product_doc = await db.card_products.find_one(
        {"_id": ObjectId(card_doc["card_product_id"])}
    )
    if product_doc is None:
        raise ValueError(f"CardProduct not found for card {card_id}")

    entitlements = BenefitEntitlements(**product_doc.get("entitlements", {}))

    # ------------------------------------------------------------------
    # 2. Build transaction from request (fill gaps with mock data)
    # ------------------------------------------------------------------
    if req.merchant_name and req.merchant_category and req.amount_usd:
        merchant_name = req.merchant_name
        merchant_category = req.merchant_category
        amount_usd = req.amount_usd
    else:
        pick = random.choice(_MOCK_MERCHANTS)
        merchant_name = req.merchant_name or pick[0]
        merchant_category = req.merchant_category or pick[1]
        amount_usd = req.amount_usd or pick[2]

    # Airline transactions get a booking ref + random delay
    is_airline = merchant_category == MerchantCategory.AIRLINE
    travel_booking_ref = req.travel_booking_ref
    flight_delay_minutes = req.flight_delay_minutes
    if is_airline:
        travel_booking_ref = travel_booking_ref or f"BK{_random_ref()}"
        if flight_delay_minutes is None:
            # 60% chance of a qualifying delay (>= 6 h = 360 min)
            flight_delay_minutes = (
                random.randint(360, 900) if random.random() < 0.6 else random.randint(0, 300)
            )

    store_refused_return = req.store_refused_return
    if store_refused_return is None:
        # 40% chance for eligible categories
        eligible_cats = {
            MerchantCategory.ELECTRONICS,
            MerchantCategory.CLOTHING,
            MerchantCategory.SPORTING_GOODS,
            MerchantCategory.JEWELRY,
            MerchantCategory.HOME_APPLIANCES,
        }
        store_refused_return = (
            random.random() < 0.4 if merchant_category in eligible_cats else False
        )

    purchased_at = req.purchased_at or utcnow()

    txn_data = TransactionBase(
        card_id=card_id,
        card_member_id=card_member_id,
        merchant_name=merchant_name,
        merchant_category=merchant_category,
        amount_usd=amount_usd,
        travel_booking_ref=travel_booking_ref,
        store_refused_return=store_refused_return,
        flight_delay_minutes=flight_delay_minutes,
        purchased_at=purchased_at,
    )

    # ------------------------------------------------------------------
    # 3. Persist transaction
    # ------------------------------------------------------------------
    txn_doc = txn_data.model_dump()
    txn_doc["status"] = TransactionStatus.PENDING
    txn_doc["created_at"] = utcnow()
    result = await db.transactions.insert_one(txn_doc)
    txn_id = str(result.inserted_id)

    txn = Transaction(
        id=txn_id,
        **txn_data.model_dump(),
        status=TransactionStatus.PENDING,
    )

    # ------------------------------------------------------------------
    # 4. Stage 1: Rules filter
    # ------------------------------------------------------------------
    filter_result = run_rules_filter(txn_data, entitlements)

    if not filter_result:
        await db.transactions.update_one(
            {"_id": ObjectId(txn_id)},
            {"$set": {"status": TransactionStatus.SKIPPED}},
        )
        return {
            "transaction": mongo_doc_to_dict(
                await db.transactions.find_one({"_id": ObjectId(txn_id)})
            ),
            "filter_passed": False,
            "filter_reason": filter_result.reason,
            "match": None,
            "claim": None,
        }

    # ------------------------------------------------------------------
    # 5. Stage 2: Match scorer
    # ------------------------------------------------------------------
    scored = default_scorer.score(txn_data, entitlements)

    if scored is None or not scored.qualifies:
        await db.transactions.update_one(
            {"_id": ObjectId(txn_id)},
            {"$set": {"status": TransactionStatus.SKIPPED}},
        )
        return {
            "transaction": mongo_doc_to_dict(
                await db.transactions.find_one({"_id": ObjectId(txn_id)})
            ),
            "filter_passed": True,
            "filter_reason": filter_result.reason,
            "match": None,
            "claim": None,
        }

    # ------------------------------------------------------------------
    # 5b. Duplicate claim guard (PDF Slide 6 — Purchase Protection requires
    #     no prior claim already filed on the same purchase).
    #     We check for any non-rejected claim on:
    #       (a) the same transaction_id, OR
    #       (b) same card_id + merchant + rounded amount + same purchase date
    #     This covers retries where the transaction_id differs but the
    #     underlying purchase is identical.
    # ------------------------------------------------------------------
    purchase_date_str = txn_data.purchased_at.strftime("%Y-%m-%d")
    duplicate_query = {
        "status": {"$ne": ClaimStatus.REJECTED.value},
        "$or": [
            {"transaction_id": txn_id},
            {
                "card_id": card_id,
                "merchant_name": txn_data.merchant_name,
                "amount_usd": txn_data.amount_usd,
                # Compare date portion only (stored as datetime)
                "purchased_at": {
                    "$gte": txn_data.purchased_at.replace(hour=0, minute=0, second=0, microsecond=0),
                    "$lt": txn_data.purchased_at.replace(hour=23, minute=59, second=59, microsecond=999999),
                },
            },
        ],
    }
    existing_claim = await db.claims.find_one(duplicate_query)
    if existing_claim is not None:
        # Mark transaction as skipped with a clear reason
        duplicate_reason = (
            f"Duplicate skipped — a claim already exists for this purchase "
            f"(claim id: {str(existing_claim['_id'])}, status: {existing_claim['status']})."
        )
        await db.transactions.update_one(
            {"_id": ObjectId(txn_id)},
            {"$set": {"status": TransactionStatus.SKIPPED, "skip_reason": duplicate_reason}},
        )
        return {
            "transaction": mongo_doc_to_dict(
                await db.transactions.find_one({"_id": ObjectId(txn_id)})
            ),
            "filter_passed": True,
            "filter_reason": filter_result.reason,
            "match": None,
            "claim": None,
            "duplicate_skipped": True,
            "duplicate_reason": duplicate_reason,
        }

    # ------------------------------------------------------------------
    # 6. Persist DetectedMatch
    # ------------------------------------------------------------------
    reason = MatchReason(
        benefit_type=scored.benefit_type,
        trigger=scored.trigger_description,
        coverage_window=scored.coverage_window_description,
        confidence_score=scored.confidence_score,
    )
    match_doc = {
        "transaction_id": txn_id,
        "card_id": card_id,
        "card_member_id": card_member_id,
        "benefit_type": scored.benefit_type.value,
        "confidence_score": scored.confidence_score,
        "reason": reason.model_dump(),
        "status": MatchStatus.DETECTED.value,
        "detected_at": utcnow(),
    }
    match_result = await db.detected_matches.insert_one(match_doc)
    match_id = str(match_result.inserted_id)

    match_obj = DetectedMatch(
        id=match_id,
        transaction_id=txn_id,
        card_id=card_id,
        card_member_id=card_member_id,
        benefit_type=scored.benefit_type,
        confidence_score=scored.confidence_score,
        reason=reason,
        status=MatchStatus.DETECTED,
    )

    # ------------------------------------------------------------------
    # 7. Stage 3: Claim pre-fill
    # ------------------------------------------------------------------
    claim_base = build_claim_draft(match_obj, txn, entitlements)
    claim_doc = claim_base.model_dump()
    claim_doc["status"] = ClaimStatus.DETECTED.value
    claim_doc["created_at"] = utcnow()
    claim_insert = await db.claims.insert_one(claim_doc)
    claim_id = str(claim_insert.inserted_id)

    # Update match status → CLAIM_DRAFTED
    await db.detected_matches.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {"status": MatchStatus.CLAIM_DRAFTED.value}},
    )

    # Update transaction status → PROCESSED
    await db.transactions.update_one(
        {"_id": ObjectId(txn_id)},
        {"$set": {"status": TransactionStatus.PROCESSED}},
    )

    # ------------------------------------------------------------------
    # 8. Write notification ("we noticed it" alert for the card member)
    # ------------------------------------------------------------------
    await create_notification(
        card_id=card_id,
        card_member_id=card_member_id,
        match_id=match_id,
        claim_id=claim_id,
        merchant_name=txn_data.merchant_name,
        amount_usd=txn_data.amount_usd,
        benefit_type=scored.benefit_type.value,
    )

    # Return full pipeline output
    claim_out = mongo_doc_to_dict(
        await db.claims.find_one({"_id": ObjectId(claim_id)})
    )
    match_out = mongo_doc_to_dict(
        await db.detected_matches.find_one({"_id": ObjectId(match_id)})
    )
    txn_out = mongo_doc_to_dict(
        await db.transactions.find_one({"_id": ObjectId(txn_id)})
    )

    return {
        "transaction": txn_out,
        "filter_passed": True,
        "filter_reason": filter_result.reason,
        "match": match_out,
        "claim": claim_out,
    }
