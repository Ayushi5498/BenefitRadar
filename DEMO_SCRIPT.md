# BenefitRadar — Live Demo Script

Three scenarios, under 2 minutes total.
Each one proves a distinct, concrete capability of the system.

---

## Setup (do this once before the demo)

```bash
# Terminal 1 — seed the demo database
cd backend
python -m app.scripts.seed_demo_scenarios

# Terminal 2 — start the API server (if not already running)
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 3 — start the frontend (if not already running)
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

> The seed script wipes the database and inserts exactly the data for the
> 3 scenarios below — same values every time, no randomness.

---

## Scenario A — Purchase Protection match (~35 seconds)

**What you are proving:** The rules filter and matching engine correctly
identify a qualifying purchase and auto-draft a complete claim with a
plain-English explanation — no manual input required.

### Steps

1. Click **Simulate Purchase** in the top nav.

2. Fill in:
   - Card → **Sarah Chen (••4242)**
   - Merchant Category → **electronics**
   - Merchant Name → `TechMart`
   - Amount (USD) → `249.00`
   - Leave all other fields blank.

3. Click **⚡ Simulate Purchase**.

### What appears on screen

- **Stage 1 — Rules Filter:** `Passed all rules checks — proceeding to matching.`
- **Stage 2 — Match:** `purchase_protection` · confidence ~90%
  - Trigger: *"Eligible purchase from 'TechMart' in category 'electronics' ($249.00)."*
  - Coverage: *"Purchase protection covers up to 120 days from purchase date."*
- **Stage 3 — Claim Pre-filled:** `$249.00 claim drafted for Purchase Protection.`
- The **bell icon** in the nav bar shows an unread badge (1 new notification).

4. Click **Review & Submit Claim →**.

5. On the Claim Detail page: verify all fields are pre-filled (Store: TechMart,
   Amount: $249.00, Benefit: Purchase Protection). Click **Submit Claim**.

6. Status tracker advances to **Being Reviewed**. Click **Approve (Demo)**.

7. Status tracker completes: ✓ Found → ✓ Submitted → ✓ Being Reviewed → ✓ Approved.
   Green banner: *"$249.00 back in your account in 3–5 business days."*

**This demonstrates:** End-to-end detection pipeline — from raw transaction
to approved payout — with zero manual claim-filling by the cardholder.

---

## Scenario B — Duplicate claim correctly blocked (~20 seconds)

**What you are proving:** The system has a claim integrity guard that prevents
the same purchase from generating a second claim, protecting against accidental
double-filing or retry abuse.

### Steps

1. Stay on **Simulate Purchase** (or navigate back to it).

2. Enter the **exact same values** as Scenario A:
   - Card → **Sarah Chen (••4242)**
   - Merchant Category → **electronics**
   - Merchant Name → `TechMart`
   - Amount (USD) → `249.00`

3. Click **⚡ Simulate Purchase**.

### What appears on screen

- **Stage 1 — Rules Filter:** passes (the transaction is still eligible).
- **⚠ Duplicate Skipped:** *"Duplicate skipped — a claim already exists for
  this purchase (claim id: ..., status: under_review)."*
- No Stage 2 match. No Stage 3 claim. No new notification.

4. Navigate to **Dashboard**. Confirm there is still exactly **1 claim** for
   Sarah Chen, not 2.

**This demonstrates:** The duplicate-claim guard works correctly — the system
fingerprints purchases by card + merchant + amount + date and blocks re-filing
while an active claim exists.

---

## Scenario C — Travel Delay match (~30 seconds)

**What you are proving:** The matching engine is not hardcoded to purchase
protection. It independently detects a completely different benefit type
(travel delay) based on a different set of trigger signals, showing the
architecture generalises across benefit types.

### Steps

1. Click **Simulate Purchase** in the top nav.

2. Fill in:
   - Card → **Marcus Webb (••8888)**
   - Merchant Category → **airline**
   - Merchant Name → `SkyBridge Airlines`
   - Amount (USD) → `520.00`
   - Booking Reference → `BKDEMO01`
   - Flight Delay (minutes) → `480`

3. Click **⚡ Simulate Purchase**.

### What appears on screen

- **Stage 1 — Rules Filter:** passes.
- **Stage 2 — Match:** `travel_delay` · confidence ~87%
  - Trigger: *"Flight delay of 480 min exceeds the 6-hour threshold on
    booking 'BKDEMO01'."*
  - Coverage: *"Claim must be filed within 60 days of the delay."*
- **Stage 3 — Claim Pre-filled:** `$500.00 claim drafted for Travel Delay Insurance.`
  - Note: amount is capped at the $500 entitlement limit even though the
    ticket was $520 — the system enforces coverage caps automatically.

4. Click **Review & Submit Claim →** and optionally approve it to show the
   full flow again.

5. Click **Metrics** in the nav. The **Claims by Benefit Type** bar chart now
   shows both Purchase Protection and Travel Delay Insurance, and the Pipeline
   Funnel reflects all transactions processed.

**This demonstrates:** The matching logic distinguishes between benefit types
based on merchant category, booking reference, and delay threshold — not a
hardcoded rule for a single benefit. Different inputs → different benefit output.

---

## One-sentence interview talking points

| Scenario | What it demonstrates |
|---|---|
| **A — Purchase Protection** | The full pipeline — rules filter, ML-ready scorer, claim pre-fill, and notification — runs end-to-end from a single transaction event with no manual steps required. |
| **B — Duplicate blocked** | A fingerprint-based claim guard prevents double-filing on the same purchase, which is a real integrity concern in any claims system. |
| **C — Travel Delay** | The matching engine is genuinely multi-benefit: it reads merchant category, booking references, and delay thresholds to select the correct coverage type independently. |

---

## Running the smoke test (to verify scenarios after code changes)

```bash
# 1. Seed first
cd backend
python -m app.scripts.seed_demo_scenarios

# 2. Make sure the server is running on port 8000, then:
python -m pytest tests/test_demo_scenarios.py -v
```

Expected output:
```
tests/test_demo_scenarios.py::test_scenario_a_purchase_protection_match PASSED
tests/test_demo_scenarios.py::test_scenario_b_duplicate_correctly_blocked PASSED
tests/test_demo_scenarios.py::test_scenario_c_travel_delay_match PASSED
3 passed
```
