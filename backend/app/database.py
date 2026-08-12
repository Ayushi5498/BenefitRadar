from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URL)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.DB_NAME]


async def close_db():
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def create_indexes():
    """Create all indexes on startup."""
    db = get_db()

    # cards
    await db.cards.create_index([("card_member_id", ASCENDING)])
    await db.cards.create_index([("card_product_id", ASCENDING)])

    # card_products
    await db.card_products.create_index([("name", ASCENDING)], unique=True)

    # transactions
    await db.transactions.create_index([("card_id", ASCENDING)])
    await db.transactions.create_index([("created_at", DESCENDING)])
    await db.transactions.create_index([("status", ASCENDING)])

    # detected_matches
    await db.detected_matches.create_index([("transaction_id", ASCENDING)])
    await db.detected_matches.create_index([("card_id", ASCENDING)])
    await db.detected_matches.create_index([("status", ASCENDING)])
    await db.detected_matches.create_index([("card_member_id", ASCENDING)])

    # claims
    await db.claims.create_index([("match_id", ASCENDING)])
    await db.claims.create_index([("card_id", ASCENDING)])
    await db.claims.create_index([("status", ASCENDING)])
    await db.claims.create_index([("card_member_id", ASCENDING)])
    await db.claims.create_index([("created_at", DESCENDING)])

    # notifications
    await db.notifications.create_index([("card_id", ASCENDING)])
    await db.notifications.create_index([("card_member_id", ASCENDING)])
    await db.notifications.create_index([("read", ASCENDING)])
    await db.notifications.create_index([("created_at", DESCENDING)])
