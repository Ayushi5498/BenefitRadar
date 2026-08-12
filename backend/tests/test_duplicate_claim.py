"""
Unit test: a second identical transaction must NOT produce a second claim.

Uses mongomock via motor's test utilities — no real MongoDB needed.
We patch get_db() to return an in-memory Motor-compatible client so the
test is fully self-contained and runs with:

    cd backend
    python -m pytest tests/test_duplicate_claim.py -v
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal async dict-backed fake collection so we don't need mongomock
# ---------------------------------------------------------------------------

class FakeCollection:
    """Tiny in-memory MongoDB collection substitute."""

    def __init__(self):
        self._docs: list[dict] = []
        self._id_counter = 0

    def _next_id(self):
        from bson import ObjectId
        return ObjectId()

    async def insert_one(self, doc: dict):
        from bson import ObjectId
        oid = self._next_id()
        doc = dict(doc)
        doc["_id"] = oid
        self._docs.append(doc)
        result = MagicMock()
        result.inserted_id = oid
        return result

    async def insert_many(self, docs):
        result = MagicMock()
        result.inserted_ids = []
        for d in docs:
            r = await self.insert_one(d)
            result.inserted_ids.append(r.inserted_id)
        return result

    async def find_one(self, query: dict = None):
        for doc in self._docs:
            if self._matches(doc, query or {}):
                return dict(doc)
        return None

    def find(self, query: dict = None):
        return FakeCursor([d for d in self._docs if self._matches(d, query or {})])

    async def update_one(self, query: dict, update: dict):
        for doc in self._docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                break

    async def count_documents(self, query: dict = None):
        return sum(1 for d in self._docs if self._matches(d, query or {}))

    async def create_index(self, *args, **kwargs):
        pass

    def _matches(self, doc: dict, query: dict) -> bool:
        for k, v in query.items():
            if k == "$or":
                if not any(self._matches(doc, sub) for sub in v):
                    return False
            elif k == "$and":
                if not all(self._matches(doc, sub) for sub in v):
                    return False
            elif isinstance(v, dict):
                # Handle operators like $ne, $gte, $lt
                doc_val = doc.get(k)
                for op, op_val in v.items():
                    if op == "$ne" and doc_val == op_val:
                        return False
                    elif op == "$gte" and (doc_val is None or doc_val < op_val):
                        return False
                    elif op == "$lt" and (doc_val is None or doc_val >= op_val):
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **kw):
        return self

    def skip(self, n):
        self._docs = self._docs[n:]
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeDB:
    def __init__(self):
        self.cards = FakeCollection()
        self.card_products = FakeCollection()
        self.transactions = FakeCollection()
        self.detected_matches = FakeCollection()
        self.claims = FakeCollection()
        self.notifications = FakeCollection()
        self.metrics_counters = FakeCollection()

    def __getitem__(self, name):
        return getattr(self, name, FakeCollection())


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def _seed_db(db: FakeDB):
    """Insert one card product + one card into the fake DB."""
    product = {
        "name": "Platinum Card",
        "network": "American Express",
        "entitlements": {
            "purchase_protection": {"enabled": True, "coverage_cap_usd": 1000.0, "coverage_window_days": 120},
            "return_protection": {"enabled": True, "coverage_cap_usd": 300.0, "extra_days": 90},
            "travel_delay": {"enabled": True, "coverage_cap_usd": 500.0, "min_delay_hours": 6, "filing_window_days": 60},
        },
    }
    prod_result = await db.card_products.insert_one(product)
    prod_id = str(prod_result.inserted_id)

    card = {
        "card_member_id": "test_member",
        "card_product_id": prod_id,
        "last_four": "0001",
        "cardholder_name": "Test User",
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    card_result = await db.cards.insert_one(card)
    return str(card_result.inserted_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_transaction_does_not_create_second_claim():
    """
    Simulate the same electronics purchase twice.
    First call → creates a claim.
    Second call → duplicate_skipped=True, no new claim created.
    """
    fake_db = FakeDB()
    card_id = await _seed_db(fake_db)

    with patch("app.services.ingestion.get_db", return_value=fake_db), \
         patch("app.services.notification_service.get_db", return_value=fake_db):
        from app.models.transaction import TransactionSimulateRequest, MerchantCategory
        from app.services.ingestion import simulate_transaction

        req = TransactionSimulateRequest(
            card_id=card_id,
            merchant_name="TechMart",
            merchant_category=MerchantCategory.ELECTRONICS,
            amount_usd=249.99,
            store_refused_return=False,
        )

        # First simulation — should produce a claim
        result1 = await simulate_transaction(req)
        assert result1["claim"] is not None, "First simulation should create a claim"
        assert result1.get("duplicate_skipped") is not True

        # Second simulation with identical details — should be duplicate-skipped
        result2 = await simulate_transaction(req)
        assert result2.get("duplicate_skipped") is True, (
            "Second identical transaction must be flagged as duplicate_skipped"
        )
        assert result2["claim"] is None, "No new claim should be created for a duplicate"

        # Confirm only ONE claim exists in the DB
        total_claims = await fake_db.claims.count_documents({})
        assert total_claims == 1, (
            f"Expected exactly 1 claim in DB, found {total_claims}"
        )


@pytest.mark.asyncio
async def test_rejected_claim_allows_new_claim():
    """
    If a prior claim was rejected, a new simulation of the same purchase
    IS allowed to create a fresh claim.
    """
    fake_db = FakeDB()
    card_id = await _seed_db(fake_db)

    with patch("app.services.ingestion.get_db", return_value=fake_db), \
         patch("app.services.notification_service.get_db", return_value=fake_db):
        from app.models.transaction import TransactionSimulateRequest, MerchantCategory
        from app.models.claim import ClaimStatus
        from app.services.ingestion import simulate_transaction

        req = TransactionSimulateRequest(
            card_id=card_id,
            merchant_name="TechMart",
            merchant_category=MerchantCategory.ELECTRONICS,
            amount_usd=249.99,
            store_refused_return=False,
        )

        # First simulation → claim created
        result1 = await simulate_transaction(req)
        assert result1["claim"] is not None

        # Manually reject that claim
        from bson import ObjectId
        claim_id = result1["claim"]["id"]
        await fake_db.claims.update_one(
            {"_id": ObjectId(claim_id)},
            {"$set": {"status": ClaimStatus.REJECTED.value}},
        )

        # Second simulation → should be allowed (prior claim was rejected)
        result2 = await simulate_transaction(req)
        assert result2.get("duplicate_skipped") is not True, (
            "A rejected claim should not block a new claim"
        )
        assert result2["claim"] is not None

        total_claims = await fake_db.claims.count_documents({})
        assert total_claims == 2
