# BenefitRadar — Design Decisions

This document explains the key architecture tradeoffs made during development.
Each section covers what a production system would need, what was built instead,
and why that was the right scope call for a working prototype.

---

## 1. Real-time streaming vs on-demand ingestion

**Production need:** A real card-benefit engine would sit downstream of a
Kafka or Cloud Pub-Sub topic fed by the issuer's authorization stream. Every
card swipe publishes a message; one or more consumer workers pick it up and run
it through the detection pipeline within seconds of the transaction clearing.

**What we built:** A single `POST /transactions/simulate` endpoint that triggers
the full pipeline synchronously on demand. There are no workers, no queue, and
no continuous feed.

**Why this was right:** The detection logic — rules filter, scorer, claim
pre-fill, notification write — lives entirely inside
`backend/app/services/ingestion.py` as a single async function,
`simulate_transaction()`. That function receives a transaction payload and
returns a result dict; it has no opinion about how the payload arrived.
Wiring it to a Kafka consumer later means writing one new adapter file that
calls `simulate_transaction()` — nothing inside the detection or matching
layer changes. The separation was deliberate: the endpoint is the entry point,
not the engine.

---

## 2. Rules-based scoring vs a trained ML classifier

**Production need:** In a live system, the scorer would be a classifier trained
on historical claims data — approved/rejected claims, merchant-category
distributions, seasonal patterns — producing calibrated confidence scores rather
than deterministic rules. scikit-learn or a lightweight TensorFlow model are the
obvious candidates once labeled data is available.

**What we built:** `RuleBasedScorer` in `backend/app/services/matcher.py`.
It implements the `MatchScorer` abstract base class, which defines a single
`score(txn, entitlements, as_of) → Optional[ScoredMatch]` interface. Confidence
scores are computed from weighted signal strength (freshness for purchase
protection, delay ratio for travel delay) rather than from learned parameters.

**Why this was right:** We don't have access to historical claims data, so
training a real model is not possible at this stage. The important decision was
to define the interface first and put the rules-based implementation behind it,
not to write rules inline in the pipeline. Any class that extends `MatchScorer`
and implements `score()` can be dropped in as `default_scorer` in `ingestion.py`
with no other changes. The interface is the production artifact here; the
`RuleBasedScorer` is explicitly a placeholder.

---

## 3. MongoDB vs the DynamoDB/MySQL split

**Production need:** The original design called for DynamoDB for fast key-value
lookups on card entitlements and claim status, and a relational store (MySQL or
Postgres) for the richer claims and transaction records that benefit from joins
and aggregations.

**What we built:** A single MongoDB instance for all five collections
(`cards`, `card_products`, `transactions`, `detected_matches`, `claims`) plus
`notifications`. Indexes are defined in `backend/app/database.py` via
`create_indexes()` on all query-critical fields: `card_id`, `status`,
`card_member_id`, `created_at`.

**Why this was right:** MongoDB's indexed document lookups on `card_id` and
`status` are operationally equivalent to the DynamoDB access pattern for this
use case — point reads by key, not scans. Using a single database halved the
infrastructure surface and removed ORM setup from the critical path. The metrics
endpoint (`GET /metrics/summary`) uses MongoDB aggregation pipelines directly,
which replaces the SQL joins a relational store would have provided. A migration
to DynamoDB + Postgres would be a data-layer concern and would not require
changes to the service or routing layers.

---

## 4. Mock transaction data vs real card-network integration

**Production need:** A real deployment would ingest transactions from an
issuer's authorization feed or a network like Stripe Issuing, receiving fields
like merchant ID, MCC code, amount, cardholder reference, and settlement
timestamp.

**What we built:** A mock transaction generator in `ingestion.py`
(`_MOCK_MERCHANTS` catalogue + random field population) and a deterministic demo
seed in `backend/app/scripts/seed_demo_scenarios.py`. The `TransactionBase`
Pydantic model in `backend/app/models/transaction.py` defines the canonical
shape: `merchant_name`, `merchant_category` (mapped from MCC), `amount_usd`,
`purchased_at`, `card_id`, `travel_booking_ref`, `store_refused_return`,
`flight_delay_minutes`.

**Why this was right:** We don't have access to a real issuer's data feed.
The schema was deliberately modeled to match what Stripe Issuing (or a similar
card API) would provide, including MCC-level category classification and
booking reference fields for travel. Integrating a real source later means
writing one inbound adapter that maps the external format onto `TransactionBase`
— the detection pipeline, scorer, and pre-fill service consume `TransactionBase`
directly and have no knowledge of where the data came from. The mock generator
is a development convenience, not a structural dependency.

---

## 5. Duplicate checking, notifications, and metrics — iterative additions

These three features were not in the initial build. After reviewing the system
against the original design spec, three gaps were identified: there was no guard
against re-filing the same claim, no mechanism to tell the cardholder a benefit
had been found, and no way to measure whether the pipeline was working.

The duplicate-claim guard was added to `ingestion.py` as a single query block
between Stage 2 and Stage 3, with no changes to the detection or matching logic.
The notification service was added as a standalone module
(`notification_service.py`) called at the end of the pipeline, keeping it
decoupled from claim creation. Metrics were implemented as MongoDB aggregation
queries in `metrics_service.py` with no schema changes — the data was already
there.

This is worth noting because it reflects how production features actually get
added: gap analysis against requirements, targeted additions that respect the
existing boundaries, verified by tests before shipping. The unit tests in
`test_duplicate_claim.py` and the E2E smoke tests in `test_demo_scenarios.py`
were written alongside the features, not afterward.

---

## If I had more time

In priority order:

**1. Train a real classifier on synthetic labeled data.**
Generate a few thousand synthetic transactions with known outcomes (approved,
rejected, duplicate, ineligible) and train a `LogisticRegression` or
`GradientBoostingClassifier` from scikit-learn on merchant category, amount,
delay magnitude, and days-since-purchase. Swap it in as a `MatchScorer`
subclass. This is the highest-value change because it would make confidence
scores actually calibrated rather than hand-tuned, and it directly tests the
extension point the codebase was designed around.

**2. Replace polling with WebSocket-based live updates.**
The dashboard and notification bell currently poll every 6 seconds. FastAPI
natively supports WebSockets; a single `/ws/events` endpoint that broadcasts
`match_created` and `notification_created` events would eliminate polling
entirely and demonstrate a more realistic real-time architecture. The frontend
`useEffect` polling hooks would be replaced by a single WebSocket hook.

**3. Kafka consumer as an alternative ingestion path.**
Write a Python consumer (using `aiokafka`) that reads from a topic and calls
`simulate_transaction()` for each message. This would complete the architecture
shown in the design spec and prove the ingestion module is genuinely transport-
agnostic. A Docker Compose file with a local Kafka broker would make it fully
self-contained.

**4. Admin UI for managing entitlement rules.**
Currently benefit entitlements (coverage caps, windows, minimum delay
thresholds) are seeded via script and can only be changed in the database
directly. A simple management page — backed by `PUT /card-products/{id}` and
`GET /card-products` endpoints — would make the system usable by a non-technical
operator and closer to production behavior where product managers configure
coverage rules without a developer.
