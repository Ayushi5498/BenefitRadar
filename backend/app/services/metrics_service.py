"""
Metrics service — derives all numbers from existing MongoDB collections.
No external analytics tool, no counters to maintain separately.
Every call runs lightweight aggregation queries against live data.
"""
from app.database import get_db


async def get_summary() -> dict:
    db = get_db()

    # ── Transactions ──────────────────────────────────────────────────
    total_transactions = await db.transactions.count_documents({})
    skipped_transactions = await db.transactions.count_documents({"status": "skipped"})
    processed_transactions = await db.transactions.count_documents({"status": "processed"})

    # Passed rules filter = anything not skipped due to filter
    # (processed = passed filter AND matched; some may pass filter but not match)
    # We track this as: total - those skipped with no match_doc
    # Since "skipped" covers both filter-fail and scorer-fail, we use
    # detected_matches to infer Stage 2 pass rate.
    filter_passed = total_transactions - skipped_transactions + processed_transactions
    # Simpler: processed = passed both stages. Skipped = failed either.
    # filter_pass_rate = processed / total (conservative proxy)

    # ── Matches ───────────────────────────────────────────────────────
    total_matches = await db.detected_matches.count_documents({})

    # ── Claims ────────────────────────────────────────────────────────
    total_claims = await db.claims.count_documents({})
    approved_claims = await db.claims.count_documents({"status": "approved"})
    rejected_claims = await db.claims.count_documents({"status": "rejected"})
    submitted_claims = await db.claims.count_documents({
        "status": {"$in": ["submitted", "under_review", "approved", "rejected"]}
    })

    # % submitted without editing (edited field added in Item 3)
    unedited_submissions = await db.claims.count_documents({
        "status": {"$in": ["submitted", "under_review", "approved", "rejected"]},
        "edited": False,
    })

    # ── Breakdown by benefit type ──────────────────────────────────────
    pipeline = [
        {"$group": {"_id": "$benefit_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    benefit_breakdown = {}
    async for doc in db.claims.aggregate(pipeline):
        benefit_breakdown[doc["_id"]] = doc["count"]

    # ── Rates ─────────────────────────────────────────────────────────
    def pct(num, denom):
        if denom == 0:
            return 0.0
        return round((num / denom) * 100, 1)

    return {
        # Raw counts
        "total_transactions": total_transactions,
        "total_matches": total_matches,
        "total_claims": total_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "submitted_claims": submitted_claims,

        # Stage pass rates
        "filter_pass_rate_pct": pct(processed_transactions, total_transactions),
        "match_rate_pct": pct(total_matches, total_transactions),

        # Form accuracy: % of submitted claims where user didn't edit
        "prefill_accuracy_pct": pct(unedited_submissions, submitted_claims) if submitted_claims else 0.0,

        # Utilization: % of detected matches that became approved claims
        "utilization_rate_pct": pct(approved_claims, total_matches),

        # Benefit breakdown
        "claims_by_benefit": benefit_breakdown,
    }
