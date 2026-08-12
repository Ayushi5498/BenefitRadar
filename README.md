# BenefitRadar — Card Benefit Activation Engine

**Team Noobies · CodeStreet Hackathon 2026 · American Express Track**

> *Your card already includes free protection you're not using.*
> *BenefitRadar finds it, matches it to your purchase, and fills in the claim for you — automatically.*

---

## Table of Contents

- [What It Does](#what-it-does)
- [Live Demo Flow](#live-demo-flow)
- [Architecture](#architecture)
- [Detection Pipeline](#detection-pipeline)
- [Benefit Logic](#benefit-logic)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [API Reference](#api-reference)
- [Frontend Screens](#frontend-screens)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [What Was Built (Full Feature List)](#what-was-built-full-feature-list)

---

## What It Does

Most credit card holders never claim the purchase protection, return protection, or travel delay insurance that comes bundled with their card — because they either don't know it exists, forget about it, or find the claims process too painful.

BenefitRadar solves all three problems:

| Problem | Our answer |
|---|---|
| You don't know | We watch every purchase and flag the ones that qualify — automatically |
| It's a hassle | We pre-fill the entire claim form; you just review and tap Submit |
| You're too late | We alert you immediately, before the coverage window expires |

---

## Live Demo Flow

```
Simulate Purchase → Detection runs → Match found → Claim pre-filled
       ↓                                                    ↓
  Bell notification appears                    Review & Submit Claim
                                                         ↓
                                              Approve (demo) → Approved ✓
```

1. Go to **Simulate Purchase** — click `⚡ Simulate Purchase` with no input (fully random) or pick a category
2. Watch the **3-stage pipeline result** appear inline (filter → match → pre-fill)
3. Click **Review & Submit Claim →** to see the pre-filled form
4. Click **Submit Claim** → then **Approve (Demo)**
5. Status tracker completes: Found → Submitted → Being Reviewed → Approved ✓
6. The **bell icon** in the nav shows unread alerts for every new match — click any to jump to the claim
7. Visit **Metrics** to see live pipeline stats and bar charts

---

## Architecture

```
Card Transaction Event
        │
        ▼
POST /transactions/simulate
        │
        ├─ 1. Resolve card + entitlements (Benefit Entitlement DB)
        │
        ├─ 2. Stage 1 — Rules Filter  (cheap, synchronous, no DB reads)
        │      • Excludes ineligible categories (restaurant, grocery, cash advance, gas)
        │      • Enforces $25 minimum amount threshold
        │      • Checks card has at least one benefit enabled
        │      └─ SKIP if fails → transaction.status = "skipped"
        │
        ├─ 3. Stage 2 — MatchScorer  (RuleBasedScorer, ML-swappable)
        │      • Priority: Travel Delay → Return Protection → Purchase Protection
        │      • Checks trigger signals + coverage window validity
        │      • Returns confidence score (0.0–1.0) + plain-English explanation
        │      └─ SKIP if no qualifying match
        │
        ├─ 4. Duplicate Claim Guard
        │      • Queries claims collection for any non-rejected claim on same purchase
        │      • Blocks duplicate on: transaction_id OR (card + merchant + amount + date)
        │      └─ SKIP with duplicate_skipped=true if found
        │
        ├─ 5. Stage 3 — Claim Pre-Fill Service
        │      • Auto-populates all claim fields from transaction + entitlements
        │      • Caps claim amount at entitlement coverage limit
        │      • Persists DetectedMatch + Claim draft
        │
        ├─ 6. Notification Service
        │      • Writes plain-English alert to notifications collection
        │      • e.g. "Your $249.99 purchase at TechMart may be covered under Purchase Protection."
        │
        └─ Response: { transaction, filter_passed, match, claim, duplicate_skipped? }
```

---

## Detection Pipeline

### Stage 1 — Rules Filter (cheap first check)

Runs on **every** transaction synchronously before anything expensive. Rejects:
- Excluded merchant categories: `restaurant`, `grocery`, `gas_station`, `cash_advance`
- Transactions below $25
- Cards with no benefits enabled

### Stage 2 — Benefit Matching (MatchScorer)

The `MatchScorer` abstract class is the designed ML extension point. `RuleBasedScorer` is the prototype implementation. To swap in a real model:

```python
class MyMLScorer(MatchScorer):
    def score(self, txn, entitlements, as_of=None):
        # load scikit-learn / TensorFlow model here
        ...

# in ingestion.py:
default_scorer = MyMLScorer()
```

Priority order (each purchase matched to exactly one benefit):
1. **Travel Delay** — most time-sensitive, checked first
2. **Return Protection** — explicit store refusal signal required
3. **Purchase Protection** — freshness-weighted confidence

### Stage 3 — Claim Pre-Fill

Auto-generates a complete `Claim` document. Every field is populated from the transaction and the card's entitlement profile. The member only reviews and taps Submit.

### Duplicate Claim Guard

Before persisting a match, queries `claims` for any non-rejected claim matching:
- Same `transaction_id`, OR
- Same `card_id` + `merchant_name` + `amount_usd` + same calendar date

If found → `duplicate_skipped: true`, no new claim created. Rejected claims do not block new ones (allows refile after rejection).

---

## Benefit Logic

Directly from PDF Slide 6:

| Benefit | Trigger Signal | Coverage Window |
|---|---|---|
| **Purchase Protection** | Eligible merchant category, no prior active claim | 90–120 days from purchase date |
| **Return Protection** | Store refused return (`store_refused_return: true`) | Store's return window + card's extra days |
| **Travel Delay Insurance** | Flight delay > threshold, booking ref present | From delay until filing deadline |

### Confidence Scoring

| Benefit | Confidence Logic |
|---|---|
| Purchase Protection | 0.55–0.90, freshness-weighted (fresher purchase = higher confidence) |
| Return Protection | Fixed 0.88 (explicit refusal signal is strong evidence) |
| Travel Delay | 0.60–1.00, scales with how far delay exceeds the threshold |

---

## Project Structure

```
BenefitRadar/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, CORS, router registration
│   │   ├── config.py                  # Pydantic settings (.env)
│   │   ├── database.py                # Motor async client, indexes
│   │   ├── seed.py                    # Demo data generator (2 products, 3 cards, 10 txns)
│   │   ├── models/
│   │   │   ├── card.py                # Card, CardProduct, BenefitEntitlements schemas
│   │   │   ├── claim.py               # Claim lifecycle schemas + ClaimSubmitRequest
│   │   │   ├── match.py               # DetectedMatch, BenefitType, MatchReason
│   │   │   ├── notification.py        # Notification schema
│   │   │   ├── transaction.py         # Transaction, MerchantCategory, TransactionStatus
│   │   │   └── common.py              # PyObjectId, mongo_doc_to_dict
│   │   ├── routers/
│   │   │   ├── transactions.py        # POST /transactions/simulate
│   │   │   ├── matches.py             # GET /matches, GET /matches/{id}
│   │   │   ├── claims.py              # GET/POST /claims, submit, approve
│   │   │   ├── cards.py               # GET /cards, GET /cards/{id}/entitlements
│   │   │   ├── notifications.py       # GET /notifications, POST /read, /read-all
│   │   │   └── metrics.py             # GET /metrics/summary
│   │   └── services/
│   │       ├── rules_filter.py        # Stage 1 — cheap rules check
│   │       ├── matcher.py             # Stage 2 — MatchScorer ABC + RuleBasedScorer
│   │       ├── claim_prefill.py       # Stage 3 — auto-draft claim document
│   │       ├── ingestion.py           # Pipeline orchestrator (all 6 stages)
│   │       ├── notification_service.py # Writes notification after match confirmed
│   │       └── metrics_service.py     # MongoDB aggregation queries for /metrics/summary
│   ├── tests/
│   │   └── test_duplicate_claim.py    # 2 unit tests for duplicate guard
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx                    # Router, nav bar, NotificationBell
    │   ├── main.jsx                   # Entry point
    │   ├── api/
    │   │   └── client.js              # Axios client — all API calls
    │   ├── components/
    │   │   ├── NotificationBell.jsx   # Bell icon, unread badge, dropdown, polling
    │   │   ├── ClaimCard.jsx          # Clickable claim row with icon + StatusBadge
    │   │   └── StatusBadge.jsx        # Colored pill for all status values
    │   └── pages/
    │       ├── Dashboard.jsx          # Stats, claims list, cards — polls every 6s
    │       ├── ClaimDetail.jsx        # Pre-filled form, editable amount, status tracker
    │       ├── Simulate.jsx           # Live pipeline trigger with stage-by-stage result
    │       └── Metrics.jsx            # KPI cards + Recharts bar charts + PDF target bars
    ├── index.html
    ├── package.json
    └── vite.config.js                 # Port 5173, proxies /api → :8000
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.111 + Python 3.11+ |
| Async DB driver | Motor 3.4 (MongoDB) |
| Data validation | Pydantic v2 |
| Database | MongoDB (local) |
| Frontend | React 18 + Vite 5 |
| HTTP client | Axios |
| Charts | Recharts |
| Routing | React Router v6 |
| Tests | pytest + pytest-asyncio |

---

## API Reference

All endpoints are documented interactively at **http://localhost:8000/docs** (Swagger UI).

### Transactions

| Method | Path | Description |
|---|---|---|
| `POST` | `/transactions/simulate` | Simulate a purchase and run the full 3-stage detection pipeline. All fields optional — omitted ones are randomly generated. |

### Matches

| Method | Path | Description |
|---|---|---|
| `GET` | `/matches` | List detected benefit matches. Filter by `card_id`, `card_member_id`, `benefit_type`. |
| `GET` | `/matches/{id}` | Get a single match by ID. |

### Claims

| Method | Path | Description |
|---|---|---|
| `GET` | `/claims` | List claims. Filter by `card_member_id`, `card_id`, `status`. |
| `GET` | `/claims/{id}` | Get a single claim. |
| `POST` | `/claims/{id}/submit` | Member confirms pre-filled claim. Accepts `{ edited: bool }` to track pre-fill accuracy. |
| `POST` | `/claims/{id}/approve` | Simulate bank approval/rejection. Accepts `{ approved: bool, reviewer_notes?: string }`. |

### Cards

| Method | Path | Description |
|---|---|---|
| `GET` | `/cards` | List all cards. |
| `GET` | `/cards/{id}` | Get a card by ID. |
| `GET` | `/cards/{id}/entitlements` | Full benefit entitlement profile: coverage types, caps, validity windows. |

### Notifications

| Method | Path | Description |
|---|---|---|
| `GET` | `/notifications` | List notifications, unread first. Filter by `card_id`, `card_member_id`, `unread_only`. |
| `POST` | `/notifications/{id}/read` | Mark a notification as read. |
| `POST` | `/notifications/read-all` | Mark all notifications as read. |

### Metrics

| Method | Path | Description |
|---|---|---|
| `GET` | `/metrics/summary` | Single JSON object with all KPIs: filter pass rate, match rate, pre-fill accuracy, utilization rate, benefit breakdown. |

---

## Frontend Screens

### Dashboard (`/`)
- 4 stat cards: Benefits Found, In Progress, Approved, Total Value
- Filterable claims list (All / detected / under_review / approved / rejected)
- Your Cards section with entitlement links
- **Polls every 6 seconds** — new claims appear without page refresh
- Live "updated HH:MM:SS" timestamp

### Simulate Purchase (`/simulate`)
- Card selector, category, merchant, amount, airline-specific fields (booking ref + delay)
- "Store refused return" checkbox for return protection scenarios
- Inline 3-stage pipeline result: Rules Filter → Match → Claim Pre-fill
- Duplicate skipped banner when a repeat purchase is detected
- Direct "Review & Submit Claim →" button after a successful match

### Claim Detail (`/claims/:id`)
- Pre-filled claim form — amount field is editable (tracks `edited` flag for metrics)
- Yellow warning banner when a pre-filled field is changed
- Visual status tracker: Found → Submitted → Being Reviewed → Approved
- Submit Claim button + Approve/Reject demo buttons
- Payout confirmation on approval

### Metrics (`/metrics`)
- 5 KPI cards: Transactions Ingested, Stage 1 Pass Rate, Stage 2 Match Rate, Pre-fill Accuracy, Utilization Rate
- 4 count cards: Matches, Submitted, Approved, Rejected
- **Pipeline Funnel bar chart** (Ingested → Matched → Submitted → Approved)
- **Claims by Benefit Type bar chart** (Purchase / Return / Travel Delay)
- **PDF Target vs Actual progress bars** (90% / 85% / 35% targets from Slide 10)
- Refreshes every 7 seconds

### Notification Bell (nav bar)
- Red unread badge with count
- Dropdown list — unread items highlighted in teal
- Click any notification → navigates straight to that claim's detail page
- "Mark all read" button
- Polls every 6 seconds

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB running on `localhost:27017`

### 1. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux

# Install dependencies
pip install -r requirements.txt

# Copy env config
copy .env.example .env         # Windows
# cp .env.example .env         # Mac / Linux

# Seed the database (2 card products, 3 cardholders, 10 transactions)
python -m app.seed

# Start the API server
uvicorn app.main:app --reload --port 8000
```

API docs: **http://localhost:8000/docs**

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: **http://localhost:5173**

### Environment Variables (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | `benefitradar` | Database name |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

**Test coverage:**

| Test | What it proves |
|---|---|
| `test_duplicate_transaction_does_not_create_second_claim` | A second identical purchase produces `duplicate_skipped: true` and no new claim in the DB |
| `test_rejected_claim_allows_new_claim` | A rejected claim does not block a new claim on the same purchase |

---

## What Was Built (Full Feature List)

### Core Detection Pipeline
- [x] **Stage 1 — Rules Filter**: fast synchronous check eliminating ineligible categories and amount floors
- [x] **Stage 2 — Benefit Matching**: `MatchScorer` abstract class (ML-swappable) + `RuleBasedScorer` implementing all 3 benefit types with trigger signals, coverage windows, and confidence scoring
- [x] **Stage 3 — Claim Pre-Fill**: auto-drafts complete claim document, caps amount at entitlement limit
- [x] **Duplicate Claim Guard**: blocks re-filing the same purchase (transaction_id OR card+merchant+amount+date fingerprint); allows refile after rejection

### Data Layer
- [x] **5 MongoDB collections**: `cards`, `card_products`, `transactions`, `detected_matches`, `claims`
- [x] **2 new collections**: `notifications`, (metrics derived from aggregation — no extra collection)
- [x] **Proper indexes** on all query paths (card_id, status, created_at, card_member_id)
- [x] **Seed script**: 2 card products (Platinum + Gold with different entitlements), 3 cardholders, 10 diverse transactions covering all benefit types and non-qualifying cases

### API (FastAPI + Pydantic v2)
- [x] `POST /transactions/simulate` — full pipeline trigger
- [x] `GET /matches`, `GET /matches/{id}`
- [x] `GET /claims`, `GET /claims/{id}`, `POST /claims/{id}/submit`, `POST /claims/{id}/approve`
- [x] `GET /cards`, `GET /cards/{id}`, `GET /cards/{id}/entitlements`
- [x] `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`
- [x] `GET /metrics/summary`
- [x] Full OpenAPI/Swagger docs at `/docs`
- [x] Proper HTTP status codes and error handling throughout

### Notifications
- [x] Plain-English alert written to DB on every confirmed match
- [x] Unread/read state, read-all endpoint
- [x] Frontend bell with unread badge, dropdown, click-to-claim navigation

### Metrics & Analytics
- [x] All KPIs derived from MongoDB aggregation (no external tool)
- [x] Filter pass rate, match rate, pre-fill accuracy (`edited` flag tracked on submit), utilization rate
- [x] Claims breakdown by benefit type
- [x] Metrics page with Recharts bar charts and PDF target progress bars

### Real-Time Feel
- [x] Dashboard polls every **6 seconds** — new claims appear without refresh
- [x] Metrics page polls every **7 seconds**
- [x] Notification bell polls every **6 seconds** independently
- [x] "Live · updated HH:MM:SS" timestamp on dashboard

### Frontend
- [x] Dashboard with stat cards, filter tabs, live polling
- [x] Claim Detail with editable pre-filled fields (tracks `edited` flag), status tracker, approve/reject
- [x] Simulate page with inline 3-stage pipeline result and duplicate banner
- [x] Metrics page with KPI cards + 2 bar charts + PDF target comparison
- [x] Notification bell component in nav bar

### Tests
- [x] 2 passing unit tests for duplicate claim guard (in-memory fake DB, no real MongoDB needed)
