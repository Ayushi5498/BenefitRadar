# BenefitRadar — Card Benefit Activation Engine

> *Your card already includes free protection you're not using.*
> *BenefitRadar finds it, matches it to your purchase, and fills in the claim for you — automatically.*

---

## Table of Contents

- [What It Does](#what-it-does)
- [Live Demo](#live-demo)
- [Architecture](#architecture)
- [Detection Pipeline](#detection-pipeline)
- [Benefit Logic](#benefit-logic)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [API Reference](#api-reference)
- [Frontend Screens](#frontend-screens)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [Feature List](#feature-list)

---

## What It Does

Most credit card holders never claim the purchase protection, return protection,
or travel delay insurance that comes bundled with their card — because they
either don't know it exists, forget about it, or find the claims process painful.

BenefitRadar solves all three problems:

| Problem | Solution |
|---|---|
| You don't know | Every purchase is checked automatically; qualifying ones are flagged instantly |
| It's a hassle | The entire claim form is pre-filled; the cardholder only reviews and taps Submit |
| You're too late | An alert fires the moment a match is found, before the coverage window expires |

---

## Live Demo

For a step-by-step walkthrough of the 3 demo scenarios (Purchase Protection,
Duplicate block, Travel Delay), see **[DEMO_SCRIPT.md](./DEMO_SCRIPT.md)**.

### Quick start for demo

```bash
# Seed the demo database (wipes and resets to clean state)
cd backend
python -m app.scripts.seed_demo_scenarios

# Start backend
uvicorn app.main:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend
npm run dev
```

Open **http://localhost:5173**, navigate to **Simulate Purchase**, and follow
the DEMO_SCRIPT.md.

---

## Architecture

```
Card Transaction Event
        │
        ▼
POST /transactions/simulate
        │
        ├─ 1. Resolve card + entitlements  (Benefit Entitlement DB)
        │
        ├─ 2. Stage 1 — Rules Filter        (cheap, synchronous, no DB reads)
        │      • Excludes ineligible categories (restaurant, grocery, cash advance)
        │      • Enforces $25 minimum amount
        │      • Checks card has at least one benefit enabled
        │      └─ SKIP if fails → transaction.status = "skipped"
        │
        ├─ 3. Stage 2 — MatchScorer         (RuleBasedScorer, ML-swappable via ABC)
        │      • Priority: Travel Delay → Return Protection → Purchase Protection
        │      • Checks trigger signals + coverage window validity
        │      • Returns confidence score (0.0–1.0) + plain-English explanation
        │      └─ SKIP if no qualifying match
        │
        ├─ 4. Duplicate Claim Guard
        │      • Queries claims for any non-rejected claim on same purchase
        │      • Fingerprint: transaction_id OR (card + merchant + amount + date)
        │      └─ Returns duplicate_skipped=true if found; no new claim created
        │
        ├─ 5. Stage 3 — Claim Pre-Fill Service
        │      • Auto-populates all claim fields from transaction + entitlements
        │      • Caps claim amount at entitlement coverage limit
        │      • Persists DetectedMatch + Claim draft
        │
        ├─ 6. Notification Service
        │      • Writes plain-English alert to notifications collection
        │      • e.g. "Your $249.00 purchase at TechMart may be covered under
        │              Purchase Protection."
        │
        └─ Response: { transaction, filter_passed, match, claim, duplicate_skipped? }
```

---

## Detection Pipeline

### Stage 1 — Rules Filter

Runs on every transaction, synchronously, before anything expensive. Rejects:
- Excluded categories: `restaurant`, `grocery`, `gas_station`, `cash_advance`
- Transactions below $25
- Cards with no benefits enabled

### Stage 2 — MatchScorer (ML extension point)

`MatchScorer` is an abstract base class — the designed seam for replacing the
rule-based logic with a trained model without changing anything else in the
pipeline:

```python
class MatchScorer(abc.ABC):
    @abc.abstractmethod
    def score(self, txn, entitlements, as_of=None) -> Optional[ScoredMatch]: ...

# Prototype implementation — swap for ML model in production:
class RuleBasedScorer(MatchScorer): ...
default_scorer: MatchScorer = RuleBasedScorer()
```

Priority order (each purchase matched to exactly one benefit):
1. **Travel Delay** — most time-sensitive, checked first
2. **Return Protection** — explicit store refusal signal required
3. **Purchase Protection** — freshness-weighted confidence

### Stage 3 — Claim Pre-Fill

Auto-generates a complete `Claim` document. Every field is populated from the
transaction and the card's entitlement profile. The cardholder only reviews and
taps Submit.

### Duplicate Claim Guard

Before persisting a match, queries `claims` for any non-rejected claim matching:
- Same `transaction_id`, OR
- Same `card_id` + `merchant_name` + `amount_usd` + same calendar date

If found → `duplicate_skipped: true`, no new claim created.
Rejected claims do not block new ones (allows refile after rejection).

---

## Benefit Logic

| Benefit | Trigger | Coverage Window |
|---|---|---|
| **Purchase Protection** | Eligible merchant category, no prior active claim | 90–120 days from purchase |
| **Return Protection** | Store refused return (`store_refused_return: true`) | Store window + card's extra days |
| **Travel Delay Insurance** | Flight delay > threshold, booking ref present | From delay until filing deadline |

### Confidence Scoring

| Benefit | Logic |
|---|---|
| Purchase Protection | 0.55–0.90, freshness-weighted (newer = higher confidence) |
| Return Protection | Fixed 0.88 (explicit refusal signal is strong) |
| Travel Delay | 0.60–1.00, scales with how far delay exceeds the threshold |

---

## Project Structure

```
BenefitRadar/
├── DEMO_SCRIPT.md                      # Step-by-step live demo walkthrough
├── demo_state.json                     # Generated by seed script (gitignored)
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app, CORS, router registration
│   │   ├── config.py                   # Pydantic settings (.env)
│   │   ├── database.py                 # Motor async client, indexes
│   │   ├── seed.py                     # General dev seed (diverse transactions)
│   │   ├── scripts/
│   │   │   └── seed_demo_scenarios.py  # Demo seed — 3 clean, deterministic scenarios
│   │   ├── models/
│   │   │   ├── card.py                 # Card, CardProduct, BenefitEntitlements
│   │   │   ├── claim.py                # Claim lifecycle + ClaimSubmitRequest
│   │   │   ├── match.py                # DetectedMatch, BenefitType, MatchReason
│   │   │   ├── notification.py         # Notification schema
│   │   │   ├── transaction.py          # Transaction, MerchantCategory
│   │   │   └── common.py               # PyObjectId, mongo_doc_to_dict
│   │   ├── routers/
│   │   │   ├── transactions.py         # POST /transactions/simulate
│   │   │   ├── matches.py              # GET /matches, GET /matches/{id}
│   │   │   ├── claims.py               # GET/POST /claims, submit, approve
│   │   │   ├── cards.py                # GET /cards, GET /cards/{id}/entitlements
│   │   │   ├── notifications.py        # GET /notifications, POST /read
│   │   │   └── metrics.py              # GET /metrics/summary
│   │   └── services/
│   │       ├── rules_filter.py         # Stage 1 — cheap rules check
│   │       ├── matcher.py              # Stage 2 — MatchScorer ABC + RuleBasedScorer
│   │       ├── claim_prefill.py        # Stage 3 — auto-draft claim document
│   │       ├── ingestion.py            # Pipeline orchestrator
│   │       ├── notification_service.py # Writes alert after match confirmed
│   │       └── metrics_service.py      # MongoDB aggregation for /metrics/summary
│   ├── tests/
│   │   ├── test_duplicate_claim.py     # Unit tests — in-memory DB, no server needed
│   │   └── test_demo_scenarios.py      # E2E smoke tests — requires running server
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx                     # Router, nav bar, NotificationBell
    │   ├── api/client.js               # Axios client — all API calls
    │   ├── components/
    │   │   ├── NotificationBell.jsx    # Bell icon, badge, dropdown, polling
    │   │   ├── ClaimCard.jsx           # Clickable claim row
    │   │   └── StatusBadge.jsx         # Colored status pill
    │   └── pages/
    │       ├── Dashboard.jsx           # Stats + claims list — polls every 6s
    │       ├── ClaimDetail.jsx         # Pre-filled form + status tracker
    │       ├── Simulate.jsx            # Live pipeline trigger with stage results
    │       └── Metrics.jsx             # KPI cards + Recharts bar charts
    ├── package.json
    └── vite.config.js                  # Port 5173, proxies /api → :8000
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Python 3.11+ |
| Async DB driver | Motor 3.x (MongoDB) |
| Data validation | Pydantic v2 |
| Database | MongoDB |
| Frontend | React 18 + Vite 5 |
| HTTP client | Axios |
| Charts | Recharts |
| Routing | React Router v6 |
| Tests | pytest + pytest-asyncio + httpx |

---

## API Reference

Full interactive docs at **http://localhost:8000/docs**.

### Transactions
| Method | Path | Description |
|---|---|---|
| `POST` | `/transactions/simulate` | Simulate a purchase and run the full 3-stage pipeline. All fields optional. |

### Matches
| Method | Path | Description |
|---|---|---|
| `GET` | `/matches` | List detected matches. Filter by `card_id`, `card_member_id`, `benefit_type`. |
| `GET` | `/matches/{id}` | Get a single match. |

### Claims
| Method | Path | Description |
|---|---|---|
| `GET` | `/claims` | List claims. Filter by `card_member_id`, `card_id`, `status`. |
| `GET` | `/claims/{id}` | Get a single claim. |
| `POST` | `/claims/{id}/submit` | Cardholder confirms. Accepts `{ edited: bool }` for pre-fill accuracy tracking. |
| `POST` | `/claims/{id}/approve` | Simulate approval. Accepts `{ approved: bool, reviewer_notes?: string }`. |

### Cards
| Method | Path | Description |
|---|---|---|
| `GET` | `/cards` | List all cards. |
| `GET` | `/cards/{id}/entitlements` | Full benefit coverage profile: types, caps, windows. |

### Notifications
| Method | Path | Description |
|---|---|---|
| `GET` | `/notifications` | List notifications, unread first. |
| `POST` | `/notifications/{id}/read` | Mark as read. |
| `POST` | `/notifications/read-all` | Mark all as read. |

### Metrics
| Method | Path | Description |
|---|---|---|
| `GET` | `/metrics/summary` | Filter pass rate, match rate, pre-fill accuracy, utilization, benefit breakdown. |

---

## Frontend Screens

### Dashboard (`/`)
- 4 stat cards: Benefits Found, In Progress, Approved, Total Value
- Filterable claims list (all / detected / under_review / approved / rejected)
- Polls every 6 seconds — new claims appear without page refresh

### Simulate Purchase (`/simulate`)
- Card selector, category, merchant, amount; airline-specific fields appear conditionally
- Inline 3-stage pipeline result after submit
- Duplicate skipped banner when a repeat purchase is detected

### Claim Detail (`/claims/:id`)
- Pre-filled form with editable amount field (tracks `edited` flag for metrics)
- Visual status tracker: Found → Submitted → Being Reviewed → Approved
- Submit + Approve/Reject demo buttons

### Metrics (`/metrics`)
- KPI cards: filter pass rate, match rate, pre-fill accuracy, utilization rate
- Pipeline Funnel bar chart (Ingested → Matched → Submitted → Approved)
- Claims by Benefit Type bar chart
- Target vs. actual progress bars
- Refreshes every 7 seconds

### Notification Bell (nav bar)
- Unread count badge, dropdown list, click navigates to claim detail
- Polls every 6 seconds

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB running on `localhost:27017`

### Backend

```bash
cd backend

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux

pip install -r requirements.txt

copy .env.example .env         # Windows
# cp .env.example .env         # Mac / Linux

# For demo: use the deterministic demo seed
python -m app.scripts.seed_demo_scenarios

# For general dev: use the broader seed
# python -m app.seed

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | `benefitradar` | Database name |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

---

## Running Tests

### Unit tests (no server needed)

```bash
cd backend
python -m pytest tests/test_duplicate_claim.py -v
```

Uses an in-memory fake MongoDB — runs in under 1 second, no external dependencies.

| Test | What it proves |
|---|---|
| `test_duplicate_transaction_does_not_create_second_claim` | Same purchase twice → second is blocked, only 1 claim in DB |
| `test_rejected_claim_allows_new_claim` | Rejected claim does not block a refile |

### E2E smoke tests (requires running server + demo seed)

```bash
# 1. Seed
cd backend
python -m app.scripts.seed_demo_scenarios

# 2. Server must be running on port 8000

# 3. Run
python -m pytest tests/test_demo_scenarios.py -v
```

| Test | What it proves |
|---|---|
| `test_scenario_a_purchase_protection_match` | Electronics purchase → purchase_protection match, claim draft, notification |
| `test_scenario_b_duplicate_correctly_blocked` | Same purchase again → `duplicate_skipped=True`, exactly 1 claim in DB |
| `test_scenario_c_travel_delay_match` | Airline + 8h delay → `travel_delay` match (different benefit type than A) |

---

## Feature List

### Core Detection Pipeline
- [x] Stage 1: Rules-based candidate filter (synchronous, no DB calls)
- [x] Stage 2: `MatchScorer` ABC + `RuleBasedScorer` — all 3 benefit types with trigger signals, coverage windows, and confidence scoring
- [x] Stage 3: Claim pre-fill — auto-drafts complete claim, caps at entitlement limit
- [x] Duplicate claim guard — blocks re-filing same purchase; allows refile after rejection

### Data Layer
- [x] 5 core MongoDB collections: `cards`, `card_products`, `transactions`, `detected_matches`, `claims`
- [x] 2 additional collections: `notifications`; metrics derived from aggregation
- [x] Indexes on all query paths
- [x] General dev seed (`app/seed.py`)
- [x] Deterministic demo seed (`app/scripts/seed_demo_scenarios.py`) — same output every run

### API
- [x] 12 endpoints across 6 routers with Pydantic v2 models
- [x] Full OpenAPI/Swagger docs at `/docs`
- [x] Proper HTTP status codes and error handling

### Notifications
- [x] Plain-English alert on every confirmed match
- [x] Read/unread state, mark-all-read endpoint
- [x] Frontend bell with badge, dropdown, click-to-claim

### Metrics
- [x] All KPIs from MongoDB aggregation (no external tool)
- [x] Pre-fill accuracy tracked via `edited` flag on claim submit
- [x] Metrics page with Recharts bar charts and target progress bars

### Real-Time Feel
- [x] Dashboard, metrics, and notification bell all poll on independent intervals
- [x] "Live · updated HH:MM:SS" timestamp on dashboard

### Tests
- [x] 2 unit tests (in-memory DB, no server required)
- [x] 3 E2E smoke tests covering all demo scenarios end-to-end
