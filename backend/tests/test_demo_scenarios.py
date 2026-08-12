"""
End-to-end smoke test for the 3 guaranteed demo scenarios.

Requires:
  1. MongoDB running on localhost:27017
  2. The FastAPI server running on port 8000:
       cd backend && uvicorn app.main:app --port 8000

The session-scoped fixture below automatically runs the demo seed script
before the test session starts, so the database is always in a clean,
known state regardless of what ran before.

Run with:
    cd backend
    python -m pytest tests/test_demo_scenarios.py -v
  or as part of the full suite:
    python -m pytest tests/ -v

What each test proves:
  test_scenario_a  — Pipeline detects a qualifying electronics purchase and
                     produces a purchase_protection claim with a notification.
  test_scenario_b  — Submitting the identical purchase a second time returns
                     duplicate_skipped=True and creates no new claim.
  test_scenario_c  — An airline transaction with an 8-hour delay is matched to
                     travel_delay — proving the matcher distinguishes benefit
                     types and is not hardcoded to a single case.
"""

import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

# ── Auto-seed before the session so the DB is always in a known state ─────────

@pytest.fixture(scope="session", autouse=True)
def seed_demo_database():
    """
    Run the demo seed script once before any test in this file executes.
    This ensures the database is wiped and repopulated with the exact
    scenario data regardless of what ran before, making the suite
    repeatable whether run alone or as part of `pytest tests/`.
    """
    result = subprocess.run(
        [sys.executable, "-m", "app.scripts.seed_demo_scenarios"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        pytest.fail(
            f"Demo seed script failed:\n{result.stdout}\n{result.stderr}"
        )
    # Reload the state file so tests pick up fresh IDs
    global _STATE
    _STATE = json.loads(_STATE_FILE.read_text())


# ── Load IDs written by the seed script ──────────────────────────────────────
_STATE_FILE = Path(__file__).resolve().parents[2] / "demo_state.json"

if not _STATE_FILE.exists():
    pytest.exit(
        "\n\ndemo_state.json not found. Run the seed script first:\n"
        "  cd backend\n"
        "  python -m app.scripts.seed_demo_scenarios\n",
        returncode=1,
    )

_STATE = json.loads(_STATE_FILE.read_text())

BASE_URL = "http://localhost:8000"
SIMULATE = f"{BASE_URL}/transactions/simulate"


# ── helpers ───────────────────────────────────────────────────────────────────

def simulate(payload: dict) -> dict:
    """POST /transactions/simulate, raise on HTTP error, return parsed JSON."""
    r = httpx.post(SIMULATE, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


# ── Scenario A ────────────────────────────────────────────────────────────────

def test_scenario_a_purchase_protection_match():
    """
    A $249 electronics purchase at TechMart on a Platinum card must:
      - pass the rules filter
      - produce a purchase_protection benefit match
      - generate a pre-filled claim draft
      - have written a notification to the DB
    """
    result = simulate(_STATE["scenario_a"])

    # Stage 1 — rules filter must pass
    assert result["filter_passed"] is True, (
        f"Rules filter rejected the transaction: {result['filter_reason']}"
    )

    # Stage 2 — match must be found
    assert result["match"] is not None, "No benefit match was returned"
    assert result["match"]["benefit_type"] == "purchase_protection", (
        f"Expected purchase_protection, got: {result['match']['benefit_type']}"
    )

    # Confidence must be meaningful (> 0.5)
    assert result["match"]["confidence_score"] > 0.5, (
        f"Confidence score too low: {result['match']['confidence_score']}"
    )

    # Reason text must be present (no black-box rule)
    assert result["match"]["reason"]["trigger"], "No trigger explanation returned"
    assert result["match"]["reason"]["coverage_window"], "No coverage window explanation"

    # Stage 3 — pre-filled claim must exist
    assert result["claim"] is not None, "No claim draft was created"
    assert result["claim"]["merchant_name"] == "TechMart"
    assert result["claim"]["amount_usd"] == 249.00
    assert result["claim"]["benefit_type"] == "Purchase Protection"
    assert result["claim"]["status"] == "detected"

    # Notification must have been written
    r = httpx.get(f"{BASE_URL}/notifications", params={"card_id": _STATE["card_a_id"]}, timeout=10)
    r.raise_for_status()
    notif_data = r.json()
    assert notif_data["total"] >= 1, "No notification written after match"
    assert "TechMart" in notif_data["notifications"][0]["message"]
    assert "249" in notif_data["notifications"][0]["message"]

    print(f"\n  ✓ Scenario A: purchase_protection match, claim={result['claim']['id']}")


# ── Scenario B ────────────────────────────────────────────────────────────────

def test_scenario_b_duplicate_correctly_blocked():
    """
    Submitting the same TechMart purchase a second time must be blocked.
    Response must include duplicate_skipped=True and claim=None.
    Total claims for card_a must remain at exactly 1.
    """
    # Scenario A must have run first (pytest runs tests in file order by default).
    # We call simulate again with the identical payload.
    result = simulate(_STATE["scenario_b"])

    assert result.get("duplicate_skipped") is True, (
        "Expected duplicate_skipped=True but got: "
        + str(result.get("duplicate_skipped"))
    )
    assert result["claim"] is None, (
        "A second claim must NOT be created for a duplicate purchase"
    )
    assert result["match"] is None, (
        "A match must NOT be recorded for a duplicate purchase"
    )

    # Exactly one claim for this card
    r = httpx.get(f"{BASE_URL}/claims", params={"card_id": _STATE["card_a_id"]}, timeout=10)
    r.raise_for_status()
    claims_data = r.json()
    assert claims_data["total"] == 1, (
        f"Expected exactly 1 claim after duplicate, found {claims_data['total']}"
    )

    print(f"\n  ✓ Scenario B: duplicate blocked, claims for card_a = 1")


# ── Scenario C ────────────────────────────────────────────────────────────────

def test_scenario_c_travel_delay_match():
    """
    An airline purchase with an 8-hour delay (480 min, threshold = 360 min)
    on a Platinum card must:
      - produce a travel_delay match (NOT purchase_protection)
      - have a confidence score >= 0.6 (minimum when threshold is just met)
      - have a pre-filled claim with the correct benefit type label
    This proves the matcher distinguishes benefit types rather than
    returning a single hardcoded result.
    """
    result = simulate(_STATE["scenario_c"])

    assert result["filter_passed"] is True, (
        f"Rules filter rejected the airline transaction: {result['filter_reason']}"
    )

    assert result["match"] is not None, "No benefit match returned for travel delay scenario"
    assert result["match"]["benefit_type"] == "travel_delay", (
        f"Expected travel_delay, got: {result['match']['benefit_type']}"
    )

    # 480 min / 360 min threshold = ratio 1.33 → confidence = 0.6 + 0.4*(1.33/2) ≈ 0.867
    assert result["match"]["confidence_score"] >= 0.6, (
        f"Confidence too low: {result['match']['confidence_score']}"
    )

    # The matched benefit type must differ from Scenario A
    assert result["match"]["benefit_type"] != "purchase_protection", (
        "Scenario C must match a DIFFERENT benefit type than Scenario A"
    )

    # Claim must reference the booking ref
    assert result["claim"] is not None, "No claim draft for travel delay"
    assert result["claim"]["benefit_type"] == "Travel Delay Insurance"
    assert result["claim"]["travel_booking_ref"] == "BKDEMO01"
    assert result["claim"]["amount_usd"] == 500.00  # capped at entitlement limit

    print(
        f"\n  ✓ Scenario C: travel_delay match, "
        f"confidence={result['match']['confidence_score']}, "
        f"claim={result['claim']['id']}"
    )
