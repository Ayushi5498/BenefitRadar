"""
Demo seed script — 3 guaranteed-working scenarios for interviews and screen recordings.

Wipes all collections and inserts exactly the data needed for:

  Scenario A — Purchase Protection match
    Card: Sarah Chen · Platinum · last four 4242
    Transaction: $249.00 Sony Headphones at "TechMart" · category: electronics
    Expected: rules filter passes → scorer returns purchase_protection →
              claim drafted + notification written

  Scenario B — Duplicate claim blocked
    Same card, same merchant, same amount, same date as Scenario A.
    Expected: pipeline detects the existing claim and returns
              duplicate_skipped=True with no new claim created.
    (This scenario's transaction is pre-inserted by the script so
     the smoke test can immediately call simulate on it and see the block.)

  Scenario C — Travel Delay match
    Card: Marcus Webb · Platinum · last four 8888
    Transaction: $520.00 ticket on "SkyBridge Airlines" · 8-hour delay
    Expected: scorer returns travel_delay (a different benefit type than A),
              proving the matching logic is not hardcoded to one case.

Run with:
    cd backend
    python -m app.scripts.seed_demo_scenarios

Outputs backend/demo_state.json so the smoke test can read exact card IDs
without hardcoding ObjectIds (they differ on every fresh run).
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.database import create_indexes


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Output file — read by smoke test to get live IDs
_STATE_FILE = Path(__file__).resolve().parents[3] / "demo_state.json"


async def seed_demo():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]

    # ── Wipe all collections for a clean slate ────────────────────────
    for col in ["card_products", "cards", "transactions",
                "detected_matches", "claims", "notifications"]:
        await db[col].drop()
    print("✓  All collections cleared")

    await create_indexes()

    # ── Card product: Platinum (all 3 benefits enabled) ───────────────
    product_doc = {
        "name": "Platinum Card",
        "network": "American Express",
        "entitlements": {
            "purchase_protection": {
                "enabled": True,
                "coverage_cap_usd": 10_000.0,
                "coverage_window_days": 120,
            },
            "return_protection": {
                "enabled": True,
                "coverage_cap_usd": 300.0,
                "extra_days": 90,
            },
            "travel_delay": {
                "enabled": True,
                "coverage_cap_usd": 500.0,
                "min_delay_hours": 6,
                "filing_window_days": 60,
            },
        },
    }
    prod_result = await db.card_products.insert_one(product_doc)
    product_id = str(prod_result.inserted_id)
    print(f"✓  Card product created: Platinum ({product_id})")

    # ── Cards ─────────────────────────────────────────────────────────
    now = utcnow()

    card_a_doc = {
        "card_member_id": "demo_member_A",
        "card_product_id": product_id,
        "last_four": "4242",
        "cardholder_name": "Sarah Chen",
        "created_at": now,
    }
    card_c_doc = {
        "card_member_id": "demo_member_C",
        "card_product_id": product_id,
        "last_four": "8888",
        "cardholder_name": "Marcus Webb",
        "created_at": now,
    }

    card_a_result = await db.cards.insert_one(card_a_doc)
    card_c_result = await db.cards.insert_one(card_c_doc)

    card_a_id = str(card_a_result.inserted_id)
    card_c_id = str(card_c_result.inserted_id)
    print(f"✓  Sarah Chen  (Scenario A/B card): {card_a_id}")
    print(f"✓  Marcus Webb (Scenario C card):   {card_c_id}")

    # ── Scenario A transaction: purchase that WILL match ─────────────
    # Purchased 2 days ago — well within the 120-day coverage window.
    # No store_refused_return, no flight delay → scorer will land on
    # purchase_protection (the fallback after travel_delay and return
    # protection both fail to fire).
    purchase_date = now - timedelta(days=2)
    txn_a_doc = {
        "card_id": card_a_id,
        "card_member_id": "demo_member_A",
        "merchant_name": "TechMart",
        "merchant_category": "electronics",
        "amount_usd": 249.00,
        "currency": "USD",
        "travel_booking_ref": None,
        "store_refused_return": False,
        "flight_delay_minutes": None,
        "purchased_at": purchase_date,
        "status": "pending",
        "created_at": now,
    }
    txn_a_result = await db.transactions.insert_one(txn_a_doc)
    txn_a_id = str(txn_a_result.inserted_id)
    print(f"✓  Scenario A transaction inserted: {txn_a_id}")

    # ── Scenario C transaction: airline with 8-hour delay ────────────
    # 8 hours = 480 minutes. Threshold is 6 hours (360 min).
    # Scorer will return travel_delay — a different benefit type than A.
    txn_c_doc = {
        "card_id": card_c_id,
        "card_member_id": "demo_member_C",
        "merchant_name": "SkyBridge Airlines",
        "merchant_category": "airline",
        "amount_usd": 520.00,
        "currency": "USD",
        "travel_booking_ref": "BKDEMO01",
        "store_refused_return": False,
        "flight_delay_minutes": 480,
        "purchased_at": now - timedelta(days=1),
        "status": "pending",
        "created_at": now,
    }
    txn_c_result = await db.transactions.insert_one(txn_c_doc)
    txn_c_id = str(txn_c_result.inserted_id)
    print(f"✓  Scenario C transaction inserted: {txn_c_id}")

    # ── Write state file for smoke test ──────────────────────────────
    state = {
        "product_id": product_id,
        "card_a_id": card_a_id,
        "card_c_id": card_c_id,
        "txn_a_id": txn_a_id,
        "txn_c_id": txn_c_id,
        # Scenario A details — smoke test passes these verbatim to /simulate
        "scenario_a": {
            "card_id": card_a_id,
            "merchant_name": "TechMart",
            "merchant_category": "electronics",
            "amount_usd": 249.00,
            "store_refused_return": False,
        },
        # Scenario B is the same payload as A — duplicate block is the outcome
        "scenario_b": {
            "card_id": card_a_id,
            "merchant_name": "TechMart",
            "merchant_category": "electronics",
            "amount_usd": 249.00,
            "store_refused_return": False,
        },
        # Scenario C
        "scenario_c": {
            "card_id": card_c_id,
            "merchant_name": "SkyBridge Airlines",
            "merchant_category": "airline",
            "amount_usd": 520.00,
            "travel_booking_ref": "BKDEMO01",
            "flight_delay_minutes": 480,
        },
    }
    _STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"\n✓  State file written → {_STATE_FILE}")

    client.close()

    print("\n" + "─" * 60)
    print("Demo seed complete. Ready for the 3 scenarios:")
    print()
    print("  A — Purchase Protection:")
    print(f"      Card: Sarah Chen ({card_a_id})")
    print(f"      POST /transactions/simulate with merchant_name=TechMart,")
    print(f"      merchant_category=electronics, amount_usd=249.00")
    print()
    print("  B — Duplicate blocked:")
    print(f"      POST /transactions/simulate with the SAME payload as A.")
    print(f"      Response: duplicate_skipped=true, claim=null")
    print()
    print("  C — Travel Delay:")
    print(f"      Card: Marcus Webb ({card_c_id})")
    print(f"      POST /transactions/simulate with merchant_name=SkyBridge Airlines,")
    print(f"      merchant_category=airline, flight_delay_minutes=480")
    print("─" * 60)


if __name__ == "__main__":
    asyncio.run(seed_demo())
