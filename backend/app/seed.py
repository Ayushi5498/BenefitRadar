"""
Seed script — populates MongoDB with realistic demo data.

Run with:
    cd backend
    python -m app.seed

Creates:
  - 2 card products (Platinum, Gold)
  - 3 card members with cards
  - 10 diverse transactions (mix of qualifying and non-qualifying)
"""
import asyncio
from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from app.config import settings
from app.database import create_indexes


async def seed():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]

    # ------------------------------------------------------------------
    # Drop existing data for a clean demo state
    # ------------------------------------------------------------------
    for col in ["card_products", "cards", "transactions", "detected_matches", "claims"]:
        await db[col].drop()
    print("Cleared existing collections.")

    await create_indexes()

    # ------------------------------------------------------------------
    # Card products
    # ------------------------------------------------------------------
    platinum_product = {
        "name": "Platinum Card",
        "network": "American Express",
        "entitlements": {
            "purchase_protection": {
                "enabled": True,
                "coverage_cap_usd": 10000.0,
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

    gold_product = {
        "name": "Gold Card",
        "network": "American Express",
        "entitlements": {
            "purchase_protection": {
                "enabled": True,
                "coverage_cap_usd": 1000.0,
                "coverage_window_days": 90,
            },
            "return_protection": {
                "enabled": True,
                "coverage_cap_usd": 300.0,
                "extra_days": 60,
            },
            "travel_delay": {
                "enabled": False,
                "coverage_cap_usd": 0.0,
                "min_delay_hours": 6,
                "filing_window_days": 0,
            },
        },
    }

    plat_result = await db.card_products.insert_one(platinum_product)
    gold_result = await db.card_products.insert_one(gold_product)
    plat_id = str(plat_result.inserted_id)
    gold_id = str(gold_result.inserted_id)
    print(f"Created card products: Platinum ({plat_id}), Gold ({gold_id})")

    # ------------------------------------------------------------------
    # Cards (3 members)
    # ------------------------------------------------------------------
    cards_data = [
        {
            "card_member_id": "member_001",
            "card_product_id": plat_id,
            "last_four": "1234",
            "cardholder_name": "Alex Johnson",
            "created_at": utcnow(),
        },
        {
            "card_member_id": "member_002",
            "card_product_id": gold_id,
            "last_four": "5678",
            "cardholder_name": "Maria Garcia",
            "created_at": utcnow(),
        },
        {
            "card_member_id": "member_003",
            "card_product_id": plat_id,
            "last_four": "9012",
            "cardholder_name": "James Lee",
            "created_at": utcnow(),
        },
    ]
    card_results = await db.cards.insert_many(cards_data)
    card_ids = [str(oid) for oid in card_results.inserted_ids]
    print(f"Created cards: {card_ids}")

    # ------------------------------------------------------------------
    # Transactions (diverse mix — some will qualify, some won't)
    # ------------------------------------------------------------------
    now = utcnow()
    transactions = [
        # SHOULD qualify → Purchase Protection
        {
            "card_id": card_ids[0],
            "card_member_id": "member_001",
            "merchant_name": "TechMart",
            "merchant_category": "electronics",
            "amount_usd": 249.99,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": False,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(days=2),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD qualify → Return Protection (store refused)
        {
            "card_id": card_ids[0],
            "card_member_id": "member_001",
            "merchant_name": "FashionForward",
            "merchant_category": "clothing",
            "amount_usd": 89.95,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": True,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(days=45),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD qualify → Travel Delay (delay = 480 min = 8h)
        {
            "card_id": card_ids[0],
            "card_member_id": "member_001",
            "merchant_name": "SkyJet Airlines",
            "merchant_category": "airline",
            "amount_usd": 480.00,
            "currency": "USD",
            "travel_booking_ref": "BKXY99",
            "store_refused_return": False,
            "flight_delay_minutes": 480,
            "purchased_at": now - timedelta(days=1),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD NOT qualify → restaurant (excluded category)
        {
            "card_id": card_ids[1],
            "card_member_id": "member_002",
            "merchant_name": "QuickBite",
            "merchant_category": "restaurant",
            "amount_usd": 32.00,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": False,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(hours=3),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD qualify → Purchase Protection (Gold card)
        {
            "card_id": card_ids[1],
            "card_member_id": "member_002",
            "merchant_name": "SoundWave Audio",
            "merchant_category": "electronics",
            "amount_usd": 399.00,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": False,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(days=10),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD NOT qualify → airline, but delay too short (2h < 6h threshold)
        {
            "card_id": card_ids[0],
            "card_member_id": "member_001",
            "merchant_name": "GlobalAir",
            "merchant_category": "airline",
            "amount_usd": 310.00,
            "currency": "USD",
            "travel_booking_ref": "BKAB12",
            "store_refused_return": False,
            "flight_delay_minutes": 120,
            "purchased_at": now - timedelta(days=5),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD qualify → Purchase Protection (jewellery)
        {
            "card_id": card_ids[2],
            "card_member_id": "member_003",
            "merchant_name": "DiamondLux Jewellers",
            "merchant_category": "jewelry",
            "amount_usd": 620.00,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": False,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(days=7),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD NOT qualify → amount too small
        {
            "card_id": card_ids[2],
            "card_member_id": "member_003",
            "merchant_name": "CoffeeCorner",
            "merchant_category": "restaurant",
            "amount_usd": 8.50,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": False,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(hours=1),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD qualify → Return Protection (sporting goods)
        {
            "card_id": card_ids[2],
            "card_member_id": "member_003",
            "merchant_name": "RunnersPro",
            "merchant_category": "sporting_goods",
            "amount_usd": 159.00,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": True,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(days=20),
            "status": "pending",
            "created_at": now,
        },
        # SHOULD qualify → Purchase Protection (home appliances)
        {
            "card_id": card_ids[1],
            "card_member_id": "member_002",
            "merchant_name": "HomeComfort",
            "merchant_category": "home_appliances",
            "amount_usd": 549.00,
            "currency": "USD",
            "travel_booking_ref": None,
            "store_refused_return": False,
            "flight_delay_minutes": None,
            "purchased_at": now - timedelta(days=3),
            "status": "pending",
            "created_at": now,
        },
    ]

    txn_results = await db.transactions.insert_many(transactions)
    print(f"Created {len(txn_results.inserted_ids)} transactions.")
    print("\nSeed complete! Card IDs for testing:")
    for i, cid in enumerate(card_ids):
        print(f"  {cards_data[i]['cardholder_name']} ({cards_data[i]['card_member_id']}): {cid}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
