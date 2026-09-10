# ARCHITECTURE — How DOT is built

The system design for the DOT backend. Read `CONTEXT.md` first if you do not know
what DOT is. The rules in `CLAUDE.md` constrain everything here.

This document is long because it carries the data model, the auth model, the domain
rules, the real-time layer, and the API contract in one place. Once implementation
starts, the natural split is to lift **§8 API Contract** into its own
`API-CONTRACT.md` — it is the section you will look up most often and the one least
coupled to the rest. Do that when it starts to hurt, not before.

---

## Contents

1. [Stack decisions](#1-stack-decisions)
2. [Folder structure and module boundaries](#2-folder-structure-and-module-boundaries)
3. [Request flow](#3-request-flow)
4. [Data model](#4-data-model)
5. [State machines](#5-state-machines)
6. [Auth and RBAC](#6-auth-and-rbac)
7. [Domain rules as enforceable server-side logic](#7-domain-rules-as-enforceable-server-side-logic)
8. [API contract](#8-api-contract)
9. [Real-time layer](#9-real-time-layer)
10. [Error handling](#10-error-handling)

---

## 1. Stack decisions

### 1.1 What the Emergent scaffold actually commits us to

Very little. `backend/server.py` is 16 lines: a FastAPI app, permissive CORS, and
`GET /api/health`. `requirements.txt` pins only `fastapi` and `uvicorn`.
`backend/.env` contains `MONGO_URL` and `DB_NAME` that **no code reads**.
`memory/PRD.md` describes the stub as existing "only so supervisor stays green
(unused by the app)".

So: the FastAPI choice is real and worth keeping. The Mongo hint is not a
commitment — there is no driver, no schema, no query, no model. Treat the database
as an open decision.

Two things from the scaffold are worth preserving:

- **Python + FastAPI.** Keeps the existing deploy shape and process supervision.
- **The `/api` prefix.** Emergent-style ingress routes `/api/*` to the backend and
  everything else to the frontend. Keeping it avoids a routing rewrite.

Everything else in `backend/` gets replaced wholesale. In particular
`allow_origins=["*"]` must go — it is incompatible with credentialed requests once
tokens exist.

### 1.2 Database: PostgreSQL vs MongoDB

**Recommendation: PostgreSQL.**

| Consideration | PostgreSQL | MongoDB |
| --- | --- | --- |
| Hash chain append integrity | A unique constraint on `(batch_id, sequence)` makes a forked or duplicated chain link *impossible to insert*. The database enforces it. | Enforced only in application code, or via a transaction the next developer forgets to use. |
| Dispute gate atomicity | `SELECT … FOR UPDATE` on the return row plus an event insert in one transaction. Standard, boring, correct. | Multi-document transactions exist but need a replica set and careful session plumbing. |
| Quantity-cap check | `SUM(quantity) … GROUP BY batch_id` against `initial_quantity`. One indexed aggregate query. | Aggregation pipeline; no constraint-level backstop. |
| Regulator audit queries | Joins across batches, returns, events, entities, alerts are the *primary* read pattern for the regulator portal. Relational joins are the native operation. | Requires either `$lookup` pipelines or denormalisation that then has to be kept in sync. |
| Entity compliance scoring | Aggregates over alerts + returns grouped by entity. Trivial SQL. | Workable, more code. |
| Enum safety | Native enum types or `CHECK` constraints reject an invalid status at write time. | No schema-level guarantee unless JSON Schema validation is configured. |
| Fit to the data | The seed is 8 clearly-related entity types with foreign keys everywhere. This is a relational dataset wearing JSON clothes. | Better suited to heterogeneous, self-contained documents. This data is neither. |
| Team familiarity / hackathon speed | SQLAlchemy + Alembic is well-trodden; migrations are a known quantity. | Faster to start with no schema, slower once the fifth rule needs a cross-collection guarantee. |

The deciding factor is that **DOT's value proposition is integrity**. A system whose
pitch is "this record cannot be silently rewritten" should put its invariants where
the database enforces them, not where a code reviewer has to notice them. Postgres
gives us unique constraints, foreign keys, check constraints, and real transactions
as a safety net under the application-level rules.

The one genuine Mongo advantage — storing a batch's events as an embedded array,
matching the frontend's `batch.events[]` shape exactly — is not worth it. We
reproduce that shape in the response serializer with a single ordered join, and we
get a queryable, constraint-protected event table in exchange.

Where JSON is genuinely the right shape (event `meta`, alert `auditTrail`,
notification payloads), use Postgres `JSONB`. Best of both.

### 1.3 Backend framework: FastAPI vs Express

**Recommendation: FastAPI.** Keeps the scaffold's language and deploy shape.
Pydantic gives typed request/response models that make the "service layer is the
contract" rule mechanically checkable. Native async suits the WebSocket fan-out.
Auto-generated OpenAPI docs at `/api/docs` are free demo material for judges.

Express would be defensible if the team were stronger in TypeScript, and sharing
types with the React frontend has real appeal — but the frontend is plain JavaScript
with no type definitions, so that benefit does not actually materialise here. Not
worth discarding the existing Python scaffold for.

### 1.4 The rest

| Concern | Choice | Why |
| --- | --- | --- |
| ORM | SQLAlchemy 2.0, async, with Alembic | Mature async support; Alembic migrations are reviewable artifacts. |
| Validation | Pydantic v2 | Already implied by FastAPI; enforces the contract at both edges. |
| Password hashing | Argon2 (`argon2-cffi` via `passlib`) | Current best practice, memory-hard. Never bcrypt-by-default, never SHA. |
| Tokens | JWT — short access, longer refresh (`python-jose`) | Stateless, works cleanly with the existing Zustand persist pattern. |
| Real-time | FastAPI WebSockets + Redis pub/sub | Fan-out to 4 roles from one event; Redis makes it multi-worker-safe from day one. |
| Hashing | SHA-256 over canonical JSON | Standard, auditable, no exotic dependency. |
| Signatures | Ed25519 (`cryptography`) | Small keys, fast, deterministic signatures. |
| Rate limiting | `slowapi` | Needed on public `/verify` endpoints. |
| Background work | FastAPI `BackgroundTasks`, plus one asyncio task for the GPS simulator | No Celery. Nothing here needs a broker-backed queue. |
| Testing | pytest + pytest-asyncio + httpx `AsyncClient` | Domain rule tests are the deliverable; see §7. |

**Deliberately excluded:** Celery, Kafka, GraphQL, a service mesh, any blockchain or
ledger anchoring, and Docker as a day-one requirement. See `BUILDPHASES.md` Phase 7
for what gets containerised later.

---

## 2. Folder structure and module boundaries

```
backend/
├── alembic/
│   ├── versions/                  # migration files, reviewed like code
│   └── env.py
├── app/
│   ├── main.py                    # FastAPI app, middleware, router registration, lifespan
│   ├── config.py                  # pydantic-settings; all env vars, one place
│   ├── deps.py                    # shared FastAPI dependencies (db session, current_user, role guards)
│   │
│   ├── api/                       # HTTP layer ONLY. No domain logic.
│   │   ├── routes_auth.py
│   │   ├── routes_batches.py
│   │   ├── routes_returns.py
│   │   ├── routes_pickups.py
│   │   ├── routes_manufacturer.py
│   │   ├── routes_alerts.py
│   │   ├── routes_entities.py
│   │   ├── routes_analytics.py
│   │   ├── routes_notifications.py
│   │   ├── routes_reference.py
│   │   ├── routes_public.py       # /api/public/* — NEVER carries an auth dependency
│   │   └── ws.py                  # WebSocket endpoint + subscription handling
│   │
│   ├── services/                  # ALL domain logic and ALL rule enforcement
│   │   ├── batch_service.py
│   │   ├── return_service.py      # dispute gate
│   │   ├── pickup_service.py
│   │   ├── manufacturer_service.py # certificate binding
│   │   ├── alert_service.py
│   │   ├── fraud_service.py       # re-entry detection + quantity-cap check
│   │   ├── event_service.py       # hash chain: the ONLY writer to the events table
│   │   ├── notification_service.py
│   │   ├── analytics_service.py
│   │   ├── entity_service.py
│   │   └── verify_service.py
│   │
│   ├── repositories/              # ALL database access. No business decisions.
│   │   ├── base.py
│   │   ├── batch_repo.py
│   │   ├── return_repo.py
│   │   ├── event_repo.py          # append-only: has insert + select, no update, no delete
│   │   ├── route_repo.py
│   │   ├── alert_repo.py
│   │   ├── entity_repo.py
│   │   └── user_repo.py
│   │
│   ├── models/                    # SQLAlchemy ORM models — persistence shape
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── entity.py              # pharmacy, distributor, manufacturer, facility, agent, vehicle
│   │   ├── batch.py
│   │   ├── event.py
│   │   ├── return_.py
│   │   ├── route.py
│   │   ├── alert.py
│   │   ├── notification.py
│   │   └── report.py
│   │
│   ├── schemas/                   # Pydantic — the wire shape the frontend already expects
│   │   ├── auth.py
│   │   ├── batch.py
│   │   ├── return_.py
│   │   ├── pickup.py
│   │   ├── alert.py
│   │   ├── analytics.py
│   │   ├── verify.py
│   │   └── common.py
│   │
│   ├── core/
│   │   ├── security.py            # password hashing, JWT encode/decode
│   │   ├── crypto.py              # canonical JSON, SHA-256 chaining, Ed25519 sign/verify
│   │   ├── errors.py              # DomainError hierarchy + HTTP exception handlers
│   │   ├── rbac.py                # role → permission matrix, single source of truth
│   │   └── realtime.py            # Redis pub/sub publisher + connection registry
│   │
│   ├── seed/
│   │   ├── seed_data.py           # mirrors frontend/src/services/seed.js exactly
│   │   └── reset.py               # powers the "Reset demo data" button
│   │
│   └── simulation/
│       └── gps_simulator.py       # server-side replacement for the client setInterval loop
│
├── tests/
│   ├── conftest.py
│   ├── test_rules_dispute_gate.py
│   ├── test_rules_certificate_binding.py
│   ├── test_rules_reentry.py
│   ├── test_rules_quantity_cap.py
│   ├── test_rules_hash_chain.py
│   ├── test_rbac.py
│   ├── test_public_verify.py
│   └── test_demo_path.py          # the full 9-step demo, end to end
│
├── requirements.txt
└── .env.example
```

### Boundary rules

The dependency direction is strictly one-way:

```
api → services → repositories → models
        ↓
      core (crypto, errors, rbac, realtime)
```

- **`api/` never imports `repositories/` or `models/`.** A router receives a
  validated request, calls exactly one service function, and serialises the result.
  If a router contains an `if` statement about business meaning, that logic is in
  the wrong file.
- **`services/` never touches the ORM session directly for queries.** It calls
  repositories. It owns transactions, rule checks, event emission, alert raising,
  and notification fan-out.
- **`repositories/` make no business decisions.** They take parameters and return
  rows or model instances. A repository never decides whether something is allowed.
- **`event_service.py` is the only module that writes events.** Everything else
  requests an event through it. This is what makes the hash chain auditable — one
  writer, one code path, one place to review.
- **`routes_public.py` never imports an auth dependency.** Enforced by a test.

---

## 3. Request flow

### Authenticated write — `POST /api/returns` as the worked example

```
Browser
  │  returnService.createReturn(batchId, data, actor)
  │  → fetch POST /api/returns   { Authorization: Bearer <access token> }
  ▼
FastAPI middleware
  │  CORS check (explicit origin allowlist, credentials allowed)
  │  request-id assigned, structured log line opened
  ▼
deps.get_current_user
  │  decode JWT → load user → attach { id, role, entity_id }
  │  401 if missing/expired, 403 if the route's role guard rejects
  ▼
api/routes_returns.py
  │  Pydantic validates the body → CreateReturnRequest
  │  calls return_service.create_return(user, batch_id, payload)
  ▼
services/return_service.py                    ← ALL RULES LIVE HERE
  │  BEGIN TRANSACTION
  │  1. batch_repo.get_for_update(batch_id)   — row lock
  │  2. ownership check: batch.pharmacy_id == user.entity_id       → 403
  │  3. state check: status in (ACTIVE, EXPIRING_SOON, EXPIRED)    → 409
  │  4. re-entry check: status == DESTROYED → fraud_service        → 409 + alert
  │  5. quantity check: 0 < quantity <= batch.quantity             → 422
  │  6. return_repo.create(...)
  │  7. batch_repo.set_status(batch, IN_RETURN)
  │  8. event_service.append(batch, RETURN_INITIATED, actor=user)  — hash + sign
  │  9. notification_service.notify(DISTRIBUTOR, ...) / (RETAILER, ...)
  │  COMMIT
  │  10. realtime.publish(...)                — AFTER commit, never inside it
  ▼
repositories/ → models/ → PostgreSQL
  ▼
Response: ReturnResponse — exactly the shape returnService.createReturn already returns
  ▼
Browser: useAppMutation invalidates queries; WebSocket pushes update other roles' views
```

Two ordering rules that matter:

- **Row lock before read-modify-write.** The dispute gate and the quantity-cap check
  both compare a stored number against an incoming one. Without `FOR UPDATE`, two
  concurrent requests can both pass the check.
- **Publish after commit.** If a real-time message goes out inside the transaction
  and the transaction then rolls back, subscribers have been told about a state that
  does not exist.

### Public read — `GET /api/public/verify/{batchId}`

```
Browser (no credentials)
  ▼
CORS → rate limiter (per IP)
  ▼
routes_public.py  — NO auth dependency, by rule
  ▼
verify_service.verify_batch(batch_id)
  │  lookup by id, then by code, then by "BATCH-" + input   (matches frontend behaviour)
  │  returns only: verdict, drug name, manufacturer, expiry, destroyed date, cert id
  ▼
{ verdict: "GENUINE" | "DESTROYED" | "NOT_FOUND", ... }
```

Public responses deliberately exclude quantities, pharmacy identity, holder chain,
event `meta`, and GPS. A patient needs a verdict, not a supply chain dossier.

---

## 4. Data model

Conventions: `snake_case` in the database, `camelCase` on the wire (Pydantic
aliases). All timestamps `TIMESTAMPTZ`, stored UTC. All primary keys are text and
carry their seeded human-readable form (`ph_1`, `BATCH-DOX-2026-A17`) — the
frontend already displays raw IDs and the demo depends on their readability.

### 4.1 `users`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `usr_<slug>` |
| `email` | `CITEXT UNIQUE NOT NULL` | login identity |
| `password_hash` | `TEXT NOT NULL` | Argon2. Never nullable, never plaintext. |
| `name` | `TEXT NOT NULL` | display name; also used as `actor.name` on events |
| `role` | `role_enum NOT NULL` | `RETAILER \| DISTRIBUTOR \| PICKUP_AGENT \| MANUFACTURER \| REGULATOR` |
| `entity_id` | `TEXT` | FK to the role's entity table; `NULL` only for regulators without jurisdiction scope |
| `is_demo` | `BOOLEAN NOT NULL DEFAULT false` | marks the 5 one-click accounts |
| `signing_public_key` | `TEXT NOT NULL` | Ed25519 public key, base64 |
| `signing_private_key` | `TEXT NOT NULL` | see §7.5 on key custody |
| `created_at` | `TIMESTAMPTZ NOT NULL` | |

Index: `(role)`, `(entity_id)`.

### 4.2 Entity tables

`pharmacies`, `distributors`, `manufacturers`, `facilities` share a shape:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `ph_1`, `dist_1`, `mfr_1`, `fac_1` |
| `name` | `TEXT NOT NULL` | |
| `city` | `TEXT NOT NULL` | doubles as the alert `district` |
| `lat`, `lng` | `DOUBLE PRECISION NOT NULL` | real Tamil Nadu coordinates |
| `address` | `TEXT` | absent on `facilities` in the current seed |
| `license_no` | `TEXT NOT NULL UNIQUE` | `TN-RTL-*`, `TN-DST-*`, `MFG-*`, `BMW-*` |
| `phone` | `TEXT` | pharmacies only |

`regulators` — new table; the frontend's `reg_1` has no backing record today:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `reg_1` |
| `name` | `TEXT` | "CDSCO — Tamil Nadu" |
| `jurisdiction` | `TEXT` | "Tamil Nadu" |
| `officer_name`, `officer_designation`, `officer_id` | `TEXT` | currently hardcoded in `regulator.jsx` Profile |

`agents`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `agent_1` |
| `distributor_id` | `TEXT FK → distributors NOT NULL` | |
| `name`, `phone` | `TEXT NOT NULL` | |
| `status` | `agent_status_enum NOT NULL` | `idle \| active \| offline` |

`vehicles`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `veh_1` |
| `distributor_id` | `TEXT FK → distributors NOT NULL` | |
| `reg_no` | `TEXT NOT NULL UNIQUE` | `TN 11 AB 1000` |
| `status` | `agent_status_enum NOT NULL` | |
| `lat`, `lng` | `DOUBLE PRECISION` | last known position |

`drugs` — reference table from `seed.js` `DRUGS`:

| Column | Type | Notes |
| --- | --- | --- |
| `key` | `TEXT PK` | `DOX`, `CIS`, `CEF`, `MER`, `ATO`, `AML`, `PAR`, `MET`, `OME` |
| `name` | `TEXT NOT NULL` | "Doxorubicin 50mg" |
| `category` | `category_enum NOT NULL` | `oncology \| antibiotics \| cardiovascular \| other` |
| `price` | `NUMERIC(10,2) NOT NULL` | unit price, INR |

### 4.3 `batches`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `BATCH-DOX-2026-A17` |
| `code` | `TEXT NOT NULL` | `DOX-2026-A17` — id minus the `BATCH-` prefix |
| `drug_key` | `TEXT FK → drugs` | |
| `drug_name` | `TEXT NOT NULL` | denormalised; frontend reads it directly |
| `category` | `category_enum NOT NULL` | denormalised |
| `unit_price` | `NUMERIC(10,2) NOT NULL` | denormalised |
| `manufacturer_id` | `TEXT FK → manufacturers NOT NULL` | |
| `manufacturer_name` | `TEXT NOT NULL` | denormalised |
| `pharmacy_id` | `TEXT FK → pharmacies` | current registering pharmacy |
| `distributor_id` | `TEXT FK → distributors` | |
| `mfg_date` | `TIMESTAMPTZ NOT NULL` | |
| `expiry_date` | `TIMESTAMPTZ NOT NULL` | |
| `initial_quantity` | `INTEGER NOT NULL CHECK (initial_quantity > 0)` | **the quantity-cap ceiling** |
| `quantity` | `INTEGER NOT NULL CHECK (quantity >= 0)` | units currently held |
| `status` | `batch_status_enum NOT NULL` | see §5.1 |
| `holder_type` | `holder_enum` | `PHARMACY \| DISTRIBUTOR \| FACILITY` |
| `holder_id`, `holder_name` | `TEXT` | serialised to the frontend as `holder: {type,id,name}` |
| `scheduled_facility_id` | `TEXT FK → facilities` | |
| `scheduled_facility_date` | `DATE` | serialised as `scheduledFacility: {id,name,date}` |
| `destroyed` | `BOOLEAN NOT NULL DEFAULT false` | frontend reads this alongside `status` |
| `destroyed_date` | `TIMESTAMPTZ` | |
| `cert_id` | `TEXT UNIQUE` | `CERT-DOX-2026-A17-2026`; unique prevents certificate reuse |
| `created_at`, `updated_at` | `TIMESTAMPTZ NOT NULL` | |

Indexes: `(pharmacy_id)`, `(manufacturer_id)`, `(distributor_id)`, `(status)`,
`(expiry_date)`, `(code)`, and a trigram or `lower(drug_name)` index for ⌘K search.

Denormalisation of `drug_name` / `manufacturer_name` / `category` / `unit_price` is
deliberate: the frontend reads them off the batch, and a batch's identity should
not silently change if reference data is later edited.

### 4.4 `events` — append-only, hash-chained

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `evt_<random>` |
| `batch_id` | `TEXT FK → batches NOT NULL` | |
| `sequence` | `INTEGER NOT NULL` | 0-based position in this batch's chain |
| `type` | `event_type_enum NOT NULL` | see §4.4.1 |
| `actor_id`, `actor_name`, `actor_role` | `TEXT NOT NULL` | serialised as `actor: {id,name,role}` |
| `ts` | `TIMESTAMPTZ NOT NULL` | |
| `gps_lat`, `gps_lng` | `DOUBLE PRECISION` | serialised as `gps: {lat,lng}` |
| `photo_hash` | `TEXT` | SHA-256 of the uploaded image, or of a deterministic placeholder |
| `meta` | `JSONB NOT NULL DEFAULT '{}'` | `{quantity}`, `{units}`, `{received}`, `{counted}`, `{facility, certId, fileName}` |
| `prev_hash` | `TEXT NOT NULL` | genesis = 64 zeros |
| `hash` | `TEXT NOT NULL` | SHA-256 hex, 64 chars |
| `signature` | `TEXT NOT NULL` | Ed25519 over `hash`, base64 |
| `signer_key_id` | `TEXT NOT NULL` | which public key verifies it |

Constraints — these are the teeth:

```sql
UNIQUE (batch_id, sequence)   -- no two events claim the same chain position
UNIQUE (hash)                 -- no duplicate links
UNIQUE (batch_id, prev_hash)  -- no forking: one event may follow any given event
```

Index: `(batch_id, sequence)` for ordered retrieval.

No `UPDATE` and no `DELETE` on this table, anywhere. Enforce it in review, and back
it with a database role that lacks those grants in production.

#### 4.4.1 Event types

`REGISTERED`, `SALE`, `RETURN_INITIATED`, `PICKUP_ASSIGNED`, `AGENT_ARRIVED`,
`PICKED_UP`, `DISTRIBUTOR_CONFIRMED`, `DISPUTE_RESOLVED`, `FORWARDED`,
`FACILITY_SCHEDULED`, `DESTROYED`, `REENTRY_BLOCKED`.

All twelve already have icons and labels in `components/common/index.jsx`
(`EVENT_META`). Adding a thirteenth means adding a frontend label — allowed, but it
is a contract change, so raise it.

### 4.5 `returns`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `ret_1` |
| `batch_id` | `TEXT FK → batches NOT NULL` | |
| `pharmacy_id` | `TEXT FK → pharmacies NOT NULL` | |
| `distributor_id` | `TEXT FK → distributors NOT NULL` | |
| `drug_name`, `category` | denormalised | frontend reads them off the return |
| `quantity_claimed` | `INTEGER NOT NULL CHECK (> 0)` | what the retailer says they are sending |
| `picked_quantity` | `INTEGER` | what the agent physically counted |
| `quantity_received` | `INTEGER` | what the distributor confirms arrived |
| `reason` | `reason_enum NOT NULL` | `EXPIRED \| DAMAGED \| RECALL` |
| `status` | `return_status_enum NOT NULL` | see §5.2 |
| `photo_hash` | `TEXT` | retailer's strip photo |
| `distributor_photo_hash` | `TEXT` | distributor's received-goods photo |
| `distributor_notes` | `TEXT` | |
| `dispute_notes` | `TEXT` | |
| `resolution_notes` | `TEXT` | **required to clear a dispute** |
| `route_id` | `TEXT FK → routes` | |
| `created_at`, `updated_at` | `TIMESTAMPTZ NOT NULL` | |

Indexes: `(pharmacy_id)`, `(distributor_id)`, `(status)`, `(batch_id)`.

Three separate quantity columns is the whole point. `quantity_claimed`,
`picked_quantity` and `quantity_received` are three independent attestations by
three different parties. Collapsing them destroys the fraud signal.

### 4.6 `routes` and `route_stops`

`routes`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `route_1` |
| `distributor_id` | `TEXT FK NOT NULL` | |
| `agent_id` | `TEXT FK → agents NOT NULL` | |
| `agent_name` | `TEXT` | denormalised |
| `vehicle_id` | `TEXT FK → vehicles NOT NULL` | |
| `vehicle_reg` | `TEXT` | denormalised |
| `status` | `route_status_enum NOT NULL` | `planned \| active \| completed` (lowercase — the frontend compares these literals) |
| `running` | `BOOLEAN NOT NULL DEFAULT false` | drives map rendering |
| `path` | `JSONB NOT NULL` | `[{lat,lng}, …]` warehouse first, then stops in order |
| `seg_index` | `INTEGER NOT NULL DEFAULT 0` | simulator position |
| `seg_t` | `DOUBLE PRECISION NOT NULL DEFAULT 0` | 0–1 within the segment |
| `pos_lat`, `pos_lng` | `DOUBLE PRECISION` | serialised as `pos: {lat,lng}` |
| `eta_min` | `INTEGER` | |
| `created_at` | `TIMESTAMPTZ NOT NULL` | |

`route_stops`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | |
| `route_id` | `TEXT FK NOT NULL` | |
| `return_id` | `TEXT FK → returns` | |
| `pharmacy_id` | `TEXT FK NOT NULL` | |
| `pharmacy_name`, `address` | `TEXT` | denormalised |
| `lat`, `lng` | `DOUBLE PRECISION NOT NULL` | |
| `order` | `INTEGER NOT NULL` | 1-based |
| `status` | `stop_status_enum NOT NULL` | `PENDING \| CURRENT \| ARRIVED \| DONE` |
| `expected_batches` | `INTEGER NOT NULL DEFAULT 1` | |
| `counted` | `INTEGER` | agent's count at this stop |

`UNIQUE (route_id, "order")`.

Serialise stops as the ordered `stops[]` array the frontend expects. Note the agent
app addresses a stop positionally as `` `${routeId}__${index}` `` — the API takes a
`stopIndex`, and the backend resolves it via `order = stopIndex + 1`. Do not change
this without changing `pages/agent.jsx`, which rule 3 forbids.

### 4.7 `alerts`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `alert_1` |
| `type` | `alert_type_enum NOT NULL` | `REENTRY \| QUANTITY_MISMATCH \| CERT_MISMATCH \| PATIENT_REPORT \| QUANTITY_CAP` |
| `severity` | `severity_enum NOT NULL` | `critical \| high \| medium \| low` |
| `status` | `alert_status_enum NOT NULL DEFAULT 'OPEN'` | `OPEN \| INVESTIGATING \| ESCALATED \| CLOSED` |
| `batch_id` | `TEXT FK → batches` | |
| `drug_name`, `drug_category` | denormalised | drives the priority sort |
| `entity_id`, `entity_name` | `TEXT` | who triggered it; `"public"` for patient reports |
| `district` | `TEXT` | |
| `manufacturer_id` | `TEXT FK → manufacturers` | |
| `rule` | `TEXT NOT NULL` | human-readable rule text shown in the regulator UI |
| `message` | `TEXT NOT NULL` | |
| `audit_trail` | `JSONB NOT NULL` | `[{action, officer, ts, notes?}]` |
| `ts` | `TIMESTAMPTZ NOT NULL` | |

Indexes: `(status)`, `(type)`, `(manufacturer_id)`, `(district)`, `(ts DESC)`.

`QUANTITY_CAP` is new — it needs a `STATUS_MAP` entry in
`components/common/index.jsx` and an option in the regulator's type filter. That is
an additive frontend change, which rule 3 permits; a redesign would not be.

**Alert ordering is a domain rule, not a UI preference.** `listAlerts` sorts
oncology → antibiotics → cardiovascular → other, then critical → high → medium →
low, then newest first. A relabelled oncology drug kills faster than a relabelled
antacid. Reproduce this ordering server-side exactly.

### 4.8 `notifications`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `TEXT PK` | `ntf_<random>` |
| `user_id` | `TEXT FK → users` | `NULL` = broadcast to the whole role |
| `role` | `role_enum NOT NULL` | the frontend fetches by role |
| `title`, `body` | `TEXT NOT NULL` | |
| `kind` | `kind_enum NOT NULL` | `info \| warning \| danger \| success` |
| `link` | `TEXT` | in-app route |
| `read` | `BOOLEAN NOT NULL DEFAULT false` | |
| `ts` | `TIMESTAMPTZ NOT NULL` | |

Index: `(role, user_id, ts DESC)`.

The frontend calls `getNotifications(role)`. Keep that signature, but scope
server-side to `role = :role AND (user_id = :me OR user_id IS NULL)` so one
pharmacy never sees another pharmacy's feed. Return at most 40, newest first,
matching the current cap.

### 4.9 `sales`, `patient_reports`, `reports`

`sales`: `id`, `batch_id`, `pharmacy_id`, `units`, `ts`.

`patient_reports`: `id`, `batch_id` (nullable — a patient may report with no
scannable code), `lat`, `lng`, `district`, `notes`, `photo_hash`, `pharmacy_name`,
`ts`, `ip_hash` (for abuse throttling; hashed, never raw).

`reports`: `id`, `title`, `region`, `category`, `created_at`, `size`,
`file_path` (nullable until PDF generation lands in a later phase).

### 4.10 Time base

`seed.js` pins `DEMO_NOW = 2026-09-15T09:30+05:30` and derives every seeded date
from it. The frontend does all its day-math against that same constant
(`daysBetween(DEMO_NOW, expiryDate)`), so if the backend seeds relative to real
wall-clock time, expiry windows and "days left" render wrong.

**Decision: pin the backend to the same constant.** Expose it as
`DEMO_NOW=2026-09-15T09:30:00+05:30` in `.env`, and derive all seeded dates from it
exactly as `seed.js` does. Keep the frontend constant unchanged. Revisit only if the
demo date drifts far enough to matter.

---

## 5. State machines

### 5.1 Batch status

```
                 ┌────────────────────────────────┐
                 ▼                                │
   [new] ──► ACTIVE ──► EXPIRING_SOON ──► EXPIRED │
               │             │              │     │
               └─────────────┴──────────────┘     │
                             │                    │
                     RETURN_INITIATED             │
                             ▼                    │
                        IN_RETURN                 │ (time passes;
                             │                    │  recomputed daily)
                    certificate bound             │
                             ▼                    │
                        DESTROYED ────────────────┘
                             │
                   scanned again → REENTRY alert, registration REFUSED
                             (status stays DESTROYED — it is terminal)
```

- `ACTIVE` → `EXPIRING_SOON` when `expiry_date - now <= 60 days`.
- `EXPIRING_SOON` → `EXPIRED` when `expiry_date < now`.
- Any of the three → `IN_RETURN` on `createReturn`.
- `IN_RETURN` → `DESTROYED` on certificate upload only.
- **`DESTROYED` is terminal.** No transition out, ever. That is what makes re-entry
  detection meaningful.

The time-driven transitions are computed by a daily job *and* derived on read, so a
batch never displays a stale status between job runs. The frontend has a
`computeStatus` helper for exactly this, currently unused — the backend owns this
logic now.

### 5.2 Return status

The frontend's service layer emits seven statuses; `seed.js` additionally emits
`ASSIGNED` and `EN_ROUTE`, and `RET_STEP_IDX` in `pharmacy.jsx` maps all nine.

**Decision: seven canonical statuses.** Store only these. Accept `ASSIGNED` and
`EN_ROUTE` on input as aliases of `SCHEDULED` for compatibility, and never emit
them. The pharmacy stepper still renders correctly because it maps `SCHEDULED` to
the same step index as `ASSIGNED`.

```
   REQUESTED ──► SCHEDULED ──► ARRIVED ──► PICKED_UP ──► CONFIRMED ──► FORWARDED
       │              │                         │            ▲
       │        (route created)                 │            │
       │                                        ▼            │
       │                                   DISPUTED ─────────┘
       │                                        │      resolution notes recorded
       └──────────── (drag back on Kanban) ─────┘             (DISPUTE_RESOLVED)
```

- `REQUESTED` — retailer created it; the distributor's inbox shows it as "New".
- `SCHEDULED` — attached to a pickup route.
- `ARRIVED` — agent marked arrival at the stop.
- `PICKED_UP` — agent recorded a physical count (`picked_quantity`).
- `CONFIRMED` — distributor's `quantity_received` matched `quantity_claimed`, **or**
  a dispute was resolved with notes.
- `DISPUTED` — mismatch. **Terminal until resolution notes are recorded.** Nothing
  advances from here.
- `FORWARDED` — handed to the manufacturer; appears in their inbox.

The distributor Kanban allows dragging between `REQUESTED`, `SCHEDULED`,
`PICKED_UP` and `CONFIRMED`. The backend must validate those transitions and must
reject any drag out of `DISPUTED` — the frontend already blocks it client-side
(`"Resolve the dispute before moving this return"`), and the server enforces the
same thing independently.

### 5.3 Route status

`planned` → `active` (on dispatch) → `completed` (last stop `DONE`). `running` is
`true` only while `active`. Stop status advances `PENDING` → `CURRENT` → `ARRIVED` →
`DONE`.

Note a conflict inherited from the mock: the client simulation loop auto-marks stops
`DONE` as the vehicle passes, while the agent also marks them `DONE` manually. On
the backend, **only the agent's action changes a stop's status.** The GPS simulator
moves the vehicle and nothing else. This removes a race the mock quietly tolerated.

---

## 6. Auth and RBAC

### 6.1 Tokens

- **Access token** — JWT, 30 minutes, claims `{sub: user_id, role, entity_id, exp,
  iat, jti}`. Sent as `Authorization: Bearer <token>`.
- **Refresh token** — JWT, 7 days, stored hashed in a `refresh_tokens` table so it
  can be revoked. Rotated on every use; reuse of a rotated token revokes the family.
- Signed HS256 with a secret from `JWT_SECRET`. Never a default, never committed.

Why not sessions and cookies: the frontend already persists auth in Zustand +
localStorage and reads `user.role` / `user.entityId` synchronously during render.
Bearer tokens drop into that shape with no restructuring. Cookies would need CSRF
protection and a rewrite of the auth store. Rule 3 forbids the rewrite.

### 6.2 Password storage

Argon2id via passlib. Never bcrypt-by-default, never a bare hash, never plaintext
anywhere — not in the database, not in logs, not in an error message, not in an
audit trail entry.

### 6.3 The login response

The frontend's `user` object is `{role, label, name, entityId, email, home, color}`.
Three of those are pure presentation: `label`, `home`, `color`.

The API returns only the real fields:

```json
{
  "accessToken": "…",
  "refreshToken": "…",
  "user": { "id": "usr_retailer", "email": "retailer@dot.in",
            "name": "Apollo Pharmacy — T. Nagar",
            "role": "RETAILER", "entityId": "ph_1" }
}
```

The frontend merges in `label` / `home` / `color` from the existing
`DEMO_ACCOUNTS`-derived map keyed by role. `ROLE_HOME` already exists in
`authStore.js` for exactly this. That keeps presentation in the frontend and
identity in the backend, and it does not change a single screen.

### 6.4 The five demo logins

They must keep working as one click, and they must not weaken real auth.

The approach: the five demo accounts are **real users with real Argon2 password
hashes**, seeded with `is_demo = true` and a known demo password from
`DEMO_PASSWORD` in `.env`. `POST /api/auth/demo-login` accepts `{role}`, looks up
the seeded demo user for that role, and issues **the same tokens by the same code
path** as a normal login.

The guards that keep this honest:

- The endpoint only ever resolves users where `is_demo = true`. It cannot be used to
  obtain a token for a real account.
- It is disabled entirely unless `ENABLE_DEMO_LOGIN=true`. That flag ships `false`
  by default and is set only in demo and development environments.
- It is rate-limited like any other auth endpoint.
- It issues no elevated scope. A demo regulator is exactly a regulator.

So the demo is a seeded shortcut through a real front door, not a second door.

### 6.5 The role → permission matrix

Single source of truth in `core/rbac.py`. Every route declares its requirement; a
route with no declaration fails closed.

| Resource / action | RETAILER | DISTRIBUTOR | PICKUP_AGENT | MANUFACTURER | REGULATOR | public |
| --- | --- | --- | --- | --- | --- | --- |
| Batches — read | own pharmacy | on own returns | on own route stops | own manufactured | **all** | — |
| Batch — register | ✅ own pharmacy | — | — | — | — | — |
| Batch — record sale | ✅ own pharmacy | — | — | — | — | — |
| Returns — read | own | own | own route stops | forwarded, own batches | **all** | — |
| Return — create | ✅ own batches | — | — | — | — | — |
| Return — receive / dispute | — | ✅ own | — | — | — | — |
| Return — resolve dispute | — | ✅ own | — | — | — | — |
| Return — forward | — | ✅ own, `CONFIRMED` only | — | — | — | — |
| Routes — read | tracking on own return only | own | **own assigned only** | live positions | **all** | — |
| Route — create / dispatch | — | ✅ own | — | — | — | — |
| Route — arrive / pickup | — | — | ✅ own assigned | — | — | — |
| Facility — schedule | — | — | — | ✅ own batches | — | — |
| Certificate — upload | — | — | — | ✅ own batches | — | — |
| Alerts — read | own entity only | own entity only | — | own batches | **all** | — |
| Alert — change status | — | — | — | — | ✅ | — |
| Entities + compliance scores | — | — | — | — | ✅ | — |
| Reports — generate | — | — | — | — | ✅ | — |
| Analytics | own scope | own scope | — | own scope | national | — |
| `verify` a batch | — | — | — | — | — | ✅ |
| Report suspicious medicine | — | — | — | — | — | ✅ |

Two layers, always both:

1. **Role guard** — a FastAPI dependency rejects the wrong role with 403 before the
   handler runs.
2. **Ownership check inside the service** — `resource.entity_id == user.entity_id`.
   A distributor with a valid token must not be able to confirm *another*
   distributor's return by guessing an ID. The role guard alone does not stop that;
   the ownership check does.

The regulator is read-only over operational data. They can change alert status and
generate reports. They cannot create returns, confirm quantities, or upload
certificates — a regulator who can edit the ledger they audit is not an auditor.

### 6.6 How `/verify` stays public

- All public endpoints live under `/api/public/*` in `routes_public.py`.
- Auth is applied **per-router**, never globally. There is no app-wide auth
  middleware that a public route has to opt out of — opt-out is the pattern that
  eventually fails closed on the wrong route.
- A test asserts every `/api/public/*` route returns non-401 with no credentials,
  and it fails the build if a new route is added without one.
- Rate limited per IP: 30/min for verification, 5/min for suspicious reports.
- Responses carry no auth-relevant headers and set no cookies.

### 6.7 Phase 1 implementation notes

Recorded here so a developer picking up Phase 2 doesn't have to rediscover
it by reading diffs.

- **Password hashing library.** §1.4 named `argon2-cffi` "via passlib".
  Passlib's argon2 backend probes `argon2.__about__`, which current
  `argon2-cffi` releases no longer ship — verification breaks outright. Phase
  1 uses `argon2-cffi`'s own `PasswordHasher` directly. Identical algorithm
  (Argon2id), identical security property, no passlib dependency.
- **Refresh tokens are JWTs whose hash is what's persisted.** A refresh
  token is itself a signed JWT (`type: "refresh"`, carries `family`, `jti`).
  Only `sha256(token)` is stored in `refresh_tokens.token_hash` — a leaked
  row is not a usable credential, same principle as a password. Rotation:
  every `/api/auth/refresh` call revokes the presented row (`revoked=true`,
  `replaced_by_id` set) and inserts a new one in the same `family_id`. Reuse
  of an already-revoked token revokes the entire family — evidence of theft
  should not let the thief's subsequently-rotated chain keep working.
- **`users.entity_id` has no database FK.** Which table it points into
  depends on `role`, and Postgres has no native polymorphic FK. This is an
  application-level guarantee (correct at seed time; any future
  user-creation path must keep it correct), not a schema one — documented on
  the model rather than silently assumed.
- **Ed25519 private keys are encrypted with a Fernet key derived from
  `SIGNING_MASTER_KEY`** (`app/core/crypto.py`: `sha256(master_key)` fed to
  `Fernet`), not stored raw. Nothing decrypts them yet — that lands with
  event signing in Phase 2. Generation only, this phase.
- **`GET /api/regulator/profile` (REGULATOR-only)** is new: it resolves
  open question #5 (§4.2) by moving the `pages/regulator.jsx` Profile
  card's hardcoded officer details into the seeded `regulators` row. It also
  doubles as the concrete example of a role-restricted endpoint for the
  RBAC test suite — Phase 1 otherwise has no ownership-bearing resource yet.
- **`core/rbac.py` vs `app/deps.py` split.** `rbac.py` holds `Role`, the
  `PERMISSION_MATRIX`, and `is_role_allowed` — framework-agnostic and unit-
  testable with no HTTP layer. `deps.py` turns that into FastAPI dependencies
  (`get_current_user`, `require_role`, `require_permission`), per this
  document's own folder-layout comment ("deps.py: db session, current_user,
  role guards"). `get_current_user` resolves the access token to the real
  `User` row on every call — never trusts token claims as identity on their
  own — so a deleted or demoted user loses access immediately, not only at
  next login.
- **Seed agent/vehicle counts.** This document's seed-data-spec table calls
  for 7 agents and 5 vehicles; `frontend/src/services/seed.js`'s actual loop
  produces 10 and 7. The backend seed follows this document's table. The
  identities the demo path depends on (`agent_1` = Ravi Kumar on `dist_1`)
  are correct either way.

---

## 7. Domain rules as enforceable server-side logic

Each rule below states its trigger, its check, its failure response, and how to test
it. All of them live in `services/`, inside the write transaction, and all assume
the caller is hostile and bypassing the UI.

### 7.1 Dispute gate

**Trigger:** `PATCH /api/returns/{id}/receive` — the distributor submits
`quantityReceived`. Also any attempt to advance a return: forward, schedule, or
certify.

**Check:**

```python
async def distributor_receive(user, return_id, payload):
    async with uow.transaction():
        ret = await return_repo.get_for_update(return_id)          # row lock
        require(ret is not None, NotFound("RETURN_NOT_FOUND"))
        require(ret.distributor_id == user.entity_id, Forbidden("NOT_YOUR_RETURN"))
        require(ret.status in (SCHEDULED, ARRIVED, PICKED_UP),
                Conflict("RETURN_NOT_RECEIVABLE", current=ret.status))
        require(0 <= payload.quantity_received <= ret.quantity_claimed * 2,
                Invalid("QUANTITY_OUT_OF_RANGE"))

        ret.quantity_received = payload.quantity_received
        ret.distributor_photo_hash = payload.photo_hash
        ret.distributor_notes = payload.notes

        if payload.quantity_received == ret.quantity_claimed:
            ret.status = CONFIRMED
            batch.holder = (DISTRIBUTOR, ret.distributor_id, distributor.name)
            await event_service.append(batch, DISTRIBUTOR_CONFIRMED, actor=user,
                                       meta={"received": payload.quantity_received})
            return {"dispute": False}

        ret.status = DISPUTED
        alert = await alert_service.raise_alert(
            type=QUANTITY_MISMATCH, severity=HIGH, batch=batch, return_=ret,
            rule="Distributor received qty ≠ pharmacy claimed qty",
            message=f"QUANTITY MISMATCH: {ret.drug_name} ({ret.batch_id}) — "
                    f"claimed {ret.quantity_claimed}, received {payload.quantity_received}")
        await notification_service.notify(REGULATOR, …)
        await notification_service.notify(RETAILER, …, user_id=pharmacy_user)
        return {"dispute": True, "alert": alert}
```

And the gate itself, called by **every** advancing operation:

```python
def assert_not_disputed(ret):
    if ret.status == DISPUTED:
        raise Conflict("CHAIN_HALTED_DISPUTE",
                       message="Quantity dispute unresolved. Chain halted.",
                       return_id=ret.id)
```

`forward_returns`, `schedule_facility`, and `upload_certificate` all call it. One
implementation, three call sites — never a copy-pasted check.

Clearing a dispute requires non-empty `resolution_notes`:

```python
require(resolution_notes and resolution_notes.strip(),
        Invalid("RESOLUTION_NOTES_REQUIRED"))
```

On success: status → `CONFIRMED`, `DISPUTE_RESOLVED` event appended, holder moves to
the distributor, and the open `QUANTITY_MISMATCH` alert is closed with an audit-trail
entry.

**Failure response:** `409 CHAIN_HALTED_DISPUTE`, or `422 RESOLUTION_NOTES_REQUIRED`.

**How to test:**
- Claimed 50, received 50 → `CONFIRMED`, no alert.
- Claimed 50, received 45 → `DISPUTED`, one `QUANTITY_MISMATCH` alert, regulator
  notified.
- `POST /api/returns/{id}/forward` on a `DISPUTED` return → 409, status unchanged.
- Same, called directly with a valid token and no UI → still 409.
- Resolve with `""` → 422. Resolve with real notes → `CONFIRMED`, forward succeeds.
- Two concurrent receive calls with different quantities → one wins, no
  double-event; assert `sequence` has no gap and no duplicate.

### 7.2 Certificate binding

**Trigger:** `POST /api/manufacturer/certificates` for a batch.

**Check** — port `certEligibility` from `manufacturerService.js` verbatim, then add
the ownership and dispute checks the frontend cannot enforce:

```python
async def assert_cert_eligible(user, batch):
    require(batch is not None, NotFound("BATCH_NOT_FOUND"))
    require(batch.manufacturer_id == user.entity_id, Forbidden("NOT_YOUR_BATCH"))
    require(batch.status != DESTROYED, Conflict("ALREADY_DESTROYED"))

    types = await event_repo.types_for_batch(batch.id)
    require({"DISTRIBUTOR_CONFIRMED", "DISPUTE_RESOLVED"} & types,
            Conflict("NOT_DISTRIBUTOR_CONFIRMED",
                     message="This batch has not been confirmed at the distributor "
                             "stage. Certificate upload blocked."))
    require("FORWARDED" in types,
            Conflict("NOT_FORWARDED",
                     message="This batch has not been forwarded to the manufacturer "
                             "yet. Certificate upload blocked."))

    ret = await return_repo.latest_for_batch(batch.id)
    assert_not_disputed(ret)                      # §7.1, reused
```

The failure `message` strings are reproduced exactly because the frontend renders
`elig.reason` directly in the blocked banner (`data-testid="cert-blocked-banner"`).

On success, in one transaction: `status = DESTROYED`, `destroyed = true`,
`destroyed_date = now`, `cert_id = f"CERT-{batch.code}-2026"`, holder → the
scheduled facility, `DESTROYED` event appended, regulator and retailer notified.

`cert_id` is `UNIQUE` in the schema — the database refuses a duplicate certificate
even if application logic is somehow bypassed. That is the no-orphan-certificate
guarantee at the storage layer.

**Failure response:** `409` with the specific code above, or `403 NOT_YOUR_BATCH`.

**How to test:**
- Fresh `ACTIVE` batch → `409 NOT_DISTRIBUTOR_CONFIRMED`.
- Confirmed but not forwarded → `409 NOT_FORWARDED`.
- Confirmed + forwarded → 200, status `DESTROYED`, `certId` set, `DESTROYED` event
  present.
- Upload twice → second call `409 ALREADY_DESTROYED`, exactly one `DESTROYED` event.
- Another manufacturer's token on the same batch → `403`.
- A batch whose return is `DISPUTED` → `409 CHAIN_HALTED_DISPUTE`.

### 7.3 Re-entry detection

**Trigger:** any point where a `DESTROYED` batch re-enters circulation —
`POST /api/batches` (registration), `POST /api/batches/{id}/sale`, an agent scan at
a stop, or a public verification of a destroyed batch.

**Check:**

```python
async def check_reentry(batch, actor, entity_id, source):
    if batch is None or batch.status != DESTROYED:
        return None
    pharmacy = await pharmacy_repo.get(entity_id)
    alert = await alert_service.raise_alert(
        type=REENTRY, severity=CRITICAL, batch=batch,
        entity_id=entity_id, entity_name=pharmacy.name if pharmacy else "Unknown pharmacy",
        district=pharmacy.city if pharmacy else "Unknown",
        manufacturer_id=batch.manufacturer_id,
        rule="Batch marked DESTROYED re-registered at a pharmacy",
        message=f"RE-ENTRY: Destroyed batch {batch.id} ({batch.drug_name}) was "
                f"scanned for registration at {pharmacy.name}")
    await event_service.append(batch, REENTRY_BLOCKED, actor=actor,
                               meta={"attemptedAt": pharmacy.name, "source": source})
    await notification_service.notify(REGULATOR, "Critical re-entry alert", alert.message,
                                      kind="danger", link=f"/regulator/alerts/{alert.id}")
    await notification_service.notify(MANUFACTURER, "Re-entry on your batch", alert.message,
                                      kind="danger", link=f"/manufacturer/batches/{batch.id}",
                                      entity_id=batch.manufacturer_id)
    await realtime.publish("alerts", alert)        # after commit
    return alert
```

The registration is **refused** — the batch is not added, quantity is not changed.
`addBatch` returns `{reentry: true, alert, batch}` and the frontend routes the user
to the alerts page, which is the existing behaviour.

Public verification of a destroyed batch returns the red verdict but does **not**
raise a REENTRY alert — a patient checking a box is not evidence that a pharmacy is
selling it. It is logged for pattern analysis. A patient who then files a suspicious
report *does* raise a `PATIENT_REPORT` alert.

**Failure response:** `409 BATCH_DESTROYED_REENTRY` with the alert in the body, and
the alert pushed over WebSocket to regulator and manufacturer channels.

**How to test:**
- Register `BATCH-DOX-2026-B04` → 409, alert exists with `severity=critical`, batch
  count unchanged, `REENTRY_BLOCKED` event appended.
- Regulator's `GET /api/alerts` shows it at the top (oncology + critical).
- A regulator WebSocket client receives the alert **within 2 seconds** — this is
  step 8 of the demo path and is a hard timing requirement.
- Manufacturer `mfr_1` receives a notification; `mfr_2` does not.
- Repeat registration → a second alert, still refused.

### 7.4 Quantity-cap check

**Why this rule exists.** Re-entry detection catches fraudsters who reuse a destroyed
batch number. Competent fraudsters do not: they print a *new* batch number on
relabelled expired stock, and destroyed-batch matching sees nothing. But they cannot
escape arithmetic. If a manufacturer produced 500 units of a batch and 640 units of
that batch have been registered across pharmacies, at least 140 units are
counterfeit — regardless of what number is printed on them. Quantity is the
invariant a forger cannot edit, because it lives across many parties' records rather
than on the box.

**Trigger:** `POST /api/batches` (registration), and a nightly sweep across all
batches.

**Check:**

```python
async def check_quantity_cap(batch_id, incoming_quantity):
    known = await batch_repo.get(batch_id)
    if known is None:
        return None                      # unknown batch — a different rule's problem
    circulating = await batch_repo.sum_registered_units(batch_id)   # SUM over all pharmacies
    total = circulating + incoming_quantity
    if total <= known.initial_quantity:
        return None
    excess = total - known.initial_quantity
    return await alert_service.raise_alert(
        type=QUANTITY_CAP, severity=CRITICAL if known.category == "oncology" else HIGH,
        batch=known, entity_id=registering_pharmacy_id,
        rule="Units in circulation exceed units ever manufactured",
        message=f"QUANTITY CAP BREACH: {known.drug_name} ({batch_id}) — "
                f"{total} units in circulation vs {known.initial_quantity} manufactured "
                f"({excess} unaccounted)")
```

Registration is **allowed** but flagged, not refused. Two reasons: a legitimate data
entry error should not block a pharmacy's workflow, and letting the record land
gives the regulator the evidence trail — refusing it would tell the fraudster which
number tripped the alarm.

`sum_registered_units` must count units registered across *all* pharmacies for that
batch id, including units already sold, and excluding units destroyed through a
completed return. Index `batches(id)` and keep this a single aggregate query.

**Failure response:** 200 with `{quantityCapBreach: true, alert}` alongside the
normal registration result. Alert pushed to regulator and manufacturer.

**How to test:**
- Batch with `initial_quantity = 50`, register 50 at pharmacy A → no alert.
- Then register 30 of the same batch id at pharmacy B → `QUANTITY_CAP` alert, excess
  30, registration still succeeds.
- Oncology batch → severity `critical`; other → `high`.
- Sold units still count toward circulation (sell 20 at A, then register 30 at B →
  alert still fires).
- Nightly sweep flags a pre-existing breach with no new registration.

### 7.5 Hash-chained event log

**What is hashed.** Canonical JSON (RFC 8785-style JSON Canonicalization Scheme:
keys sorted lexicographically, no insignificant whitespace, UTF-8, numbers in
shortest round-trip form) over exactly these fields, in this order:

```json
{
  "actor": {"id": "…", "name": "…", "role": "…"},
  "batchId": "BATCH-DOX-2026-A17",
  "gps": {"lat": 13.0418, "lng": 80.2341},
  "meta": {"quantity": 50},
  "photoHash": "…",
  "prevHash": "…",
  "sequence": 3,
  "ts": "2026-09-15T09:30:00.000Z",
  "type": "RETURN_INITIATED"
}
```

Canonicalisation is what makes verification reproducible: two implementations must
produce byte-identical input, or every signature is worthless. Do not hash a Python
`dict` repr, do not hash `json.dumps` with default settings, and do not include
fields that are assigned after insert.

```python
hash      = sha256(canonical_json(payload)).hexdigest()      # 64 hex chars
signature = ed25519_sign(actor_private_key, bytes.fromhex(hash))
```

Genesis `prev_hash` is 64 zeros (the frontend mock uses a shortened
`0x0000000000000000`; the backend uses full-width SHA-256 and the UI renders
whatever length it receives).

**Keys.** Each entity gets an Ed25519 keypair at seed time. Private keys are stored
encrypted at rest with a master key from `SIGNING_MASTER_KEY` in `.env`, and are
only ever loaded inside `event_service`. This is honest about what it is: the server
signs on the actor's behalf, which proves *the server recorded this actor's action
in this order* — it is not a client-side signature and does not claim to be. Real
client-held keys are a post-hackathon evolution and are noted as such in
`BUILDPHASES.md`. The tamper-evidence property — that history cannot be silently
rewritten — holds either way.

**Verification.** `GET /api/batches/{id}/verify-chain` walks the batch's events in
`sequence` order and asserts, for each: `prev_hash` equals the previous event's
`hash`; recomputing the hash from stored fields reproduces `hash`; the signature
verifies against `signer_key_id`'s public key. Returns
`{valid, brokenAtSequence, checked}`.

**Why this gives tamper-evidence without a blockchain.** To alter event *n*, an
attacker must recompute event *n*'s hash, which changes event *n+1*'s `prev_hash`,
which changes its hash, and so on to the head — so a single edit requires forging
every subsequent link. Each of those links carries an Ed25519 signature from a
*different* actor's key, so forging the chain requires every one of those actors'
private keys, not just database write access. The `UNIQUE (batch_id, prev_hash)`
constraint additionally makes it impossible to insert a competing fork and leave the
original in place.

A blockchain would add distributed consensus over *who may append*. DOT does not
need that: CDSCO is the trusted authority by statute, participants are licensed and
known, and the property that actually matters — "this record cannot be silently
rewritten, and any rewrite is detectable" — is fully delivered by a signed hash
chain in Postgres. Adding a chain would add cost, latency and operational risk to
buy a property the regulatory model already provides.

**How to test:**
- Append 5 events, run `verify-chain` → `valid: true`.
- `UPDATE events SET meta = … WHERE sequence = 2` directly in SQL → `verify-chain`
  returns `valid: false, brokenAtSequence: 2`.
- Delete a middle event → detected as a sequence gap.
- Attempt to insert a second event with an existing `prev_hash` → database rejects
  it (unique violation), proving no forking.
- Tamper with a signature → verification fails at that event.
- Concurrency: 10 parallel appends on one batch → sequences 0–9 with no gap and no
  duplicate, chain valid. (Row-lock the batch during append.)

#### 7.5.1 Phase 2 implementation notes

Recorded here so Phase 3 doesn't have to rediscover it by reading diffs.

- **Event actors are entities, not login users.** The frontend already
  constructs `actor` as `{id: entityId, name: user.name, role}` (e.g. a
  pharmacy's id, not the logged-in account's id) — see
  `pages/pharmacy.jsx`'s calls to `addBatch`/`simulateSale`. So the Ed25519
  keypair an event is actually signed with lives on the acting entity
  (`pharmacies`/`distributors`/`manufacturers`/`agents` each got a
  `signing_public_key`/`signing_private_key` column pair in Phase 2's
  migration) rather than on `users`, where Phase 1 first placed it per
  §4.1. `users.signing_*` is harmless and unused by event signing as of
  Phase 2. `signer_key_id` on an event is the acting entity's id; chain
  verification resolves the public key by looking up that id in the table
  matching the event's `actor_role`.
- **Canonical `ts` formatting is truncated to milliseconds before it is
  ever hashed or stored.** PostgreSQL's `TIMESTAMPTZ` keeps microsecond
  precision; truncating first (`event_service._format_ts`) guarantees that
  reloading the stored value and reformatting it for a later
  `verify-chain` call reproduces the exact same string the original hash
  was computed over.
- **Deterministic `photoHash` placeholder.** No real photo upload exists
  yet (cut list). The placeholder is `sha256(batchId:type:sequence)` —
  keyed by `sequence`, not wall-clock time, specifically so a reseeded
  batch's events hash identically on every reset.
- **GPS defaults to the acting entity's own seeded coordinates**, not a
  random jitter — `seed.js`'s `Math.random()` jitter is exactly the kind
  of nondeterminism BUILDPHASES.md's seed spec forbids. A pharmacy's
  events happen at that pharmacy's coordinates; a distributor's at the
  distributor's; and so on.
- **`verify_chain` reports every independent failure it finds**, not just
  the first: sequence-gap, prev-hash-mismatch, hash-mismatch, and
  signature-invalid are checked separately per event, so a single tampered
  field is diagnosed precisely (e.g. editing only `meta` correctly reports
  `HASH_MISMATCH` without also reporting `SIGNATURE_INVALID`, because the
  stored signature is still valid over the stored, unchanged hash).
- **Status derivation happens on every read, against `DEMO_NOW`, not real
  wall-clock time** — consistent with pinning the whole system to that
  constant (§4.10). No scheduler exists or is planned before it's needed;
  "derive on read" alone is sufficient for a demo that isn't running
  through real months of wall-clock time.
- **A duplicate batch id at registration is a flat `409
  BATCH_ALREADY_EXISTS`**, regardless of the existing batch's status. Phase
  3's re-entry detection replaces only the `DESTROYED` branch of that
  check with the alert-and-refuse behavior in §7.3 — everything else about
  registration is unchanged.

### 7.6 Rule interaction summary

| Operation | Rules that must pass |
| --- | --- |
| Register batch | re-entry, quantity cap, ownership |
| Create return | ownership, batch state, quantity ≤ held, re-entry |
| Agent pickup | route assignment ownership, stop state |
| Distributor receive | ownership, return state, **dispute gate** |
| Forward | ownership, status `CONFIRMED`, **not disputed** |
| Schedule facility | ownership, forwarded, **not disputed** |
| Upload certificate | ownership, **certificate binding**, **not disputed**, not destroyed |
| Any of the above | hash chain append with signature |

---

## 8. API contract

All routes are prefixed `/api`. Every response body matches what the corresponding
frontend service function already returns — that is the contract.

Legend: **A** = authenticated, **P** = public, role in brackets.

### 8.1 Auth

| Endpoint | Method | Request | Response |
| --- | --- | --- | --- |
| `/api/auth/login` | POST | `{email, password}` | `{accessToken, refreshToken, user}` |
| `/api/auth/demo-login` | POST | `{role}` | same as login (gated by `ENABLE_DEMO_LOGIN`) |
| `/api/auth/refresh` | POST | `{refreshToken}` | `{accessToken, refreshToken}` |
| `/api/auth/logout` | POST | `{refreshToken}` | `{ok: true}` |
| `/api/auth/me` | GET | — | `{user}` |

### 8.2 Batches — `batchService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `listBatches()` | `GET /api/batches` **A** | Scoped by role per §6.5. Supports `?pharmacyId=&manufacturerId=&status=&q=&limit=&offset=`. Returns `Batch[]` **including** `events[]`. |
| `getBatch(id)` | `GET /api/batches/{id}` **A** | Accepts id **or** code. Returns `Batch` with ordered `events[]`, or 404. |
| `searchAll(q)` | `GET /api/search?q=` **A** | `[{type:"batch"\|"pharmacy", id, title, subtitle, status}]`, max 12. |
| `addBatch(payload, actor, pharmacyId)` | `POST /api/batches` **A** [RETAILER] | Body `{batchId, drugName, drugKey, category, unitPrice, manufacturerId, manufacturerName, mfgDate, expiryDate, quantity}`. Returns `{reentry, batch, alert?, quantityCapBreach?}`. |
| `simulateSale(batchId, units, actor)` | `POST /api/batches/{id}/sale` **A** [RETAILER] | Body `{units}`. Returns updated `Batch` or 409 `INSUFFICIENT_STOCK`. |
| *(new)* | `GET /api/batches/{id}/verify-chain` **A** [REGULATOR] | `{valid, brokenAtSequence, checked}`. |

`listBatches` currently returns every batch unfiltered — with ~44 seeded batches
that is fine, but the endpoint must paginate and must scope by role. The frontend
filters client-side today; server-side scoping is additive and does not change any
screen.

### 8.3 Returns — `returnService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `listReturns(filter)` | `GET /api/returns?pharmacyId=&distributorId=&status=` **A** | Sorted `createdAt` desc. |
| `getReturn(id)` | `GET /api/returns/{id}` **A** | Returns the return joined with `batch`, `pharmacy`, `distributor`. |
| `createReturn(batchId, data, actor)` | `POST /api/returns` **A** [RETAILER] | Body `{batchId, quantity, distributorId, reason, photoHash}`. Returns `Return`. |
| `distributorReceive(id, {…})` | `PATCH /api/returns/{id}/receive` **A** [DISTRIBUTOR] | Body `{quantityReceived, photoHash, notes}`. Returns `{dispute, alert?}`. |
| `resolveDispute(id, notes)` | `PATCH /api/returns/{id}/resolve` **A** [DISTRIBUTOR] | Body `{resolutionNotes}`. 422 if blank. |
| `forwardReturns(ids[], actor)` | `POST /api/returns/forward` **A** [DISTRIBUTOR] | Body `{returnIds}`. Returns `{ok, forwarded[], skipped[]}` — the mock silently skipped non-`CONFIRMED` returns; the API reports them instead. |
| `setReturnStatus(id, status, actor)` | `PATCH /api/returns/{id}/status` **A** [DISTRIBUTOR] | Kanban drag. Validates the transition; **rejects any move out of `DISPUTED`**. |

### 8.4 Pickups — `pickupService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `listRoutes(filter)` | `GET /api/routes?distributorId=&agentId=` **A** | Agents see only their own. |
| `getRoute(id)` | `GET /api/routes/{id}` **A** | Includes `stops[]`, `path`, `pos`, `etaMin`, `running`. |
| `listFleet(distributorId)` | `GET /api/fleet?distributorId=` **A** | `{vehicles, agents}`. |
| `createRoute({…})` | `POST /api/routes` **A** [DISTRIBUTOR] | Body `{distributorId, returnIds, agentId, vehicleId, manualOrder}`. Nearest-neighbour ordering when `manualOrder` is false. Sets the returns to `SCHEDULED`. |
| `dispatchRoute(routeId)` | `POST /api/routes/{id}/dispatch` **A** [DISTRIBUTOR, PICKUP_AGENT] | Agent "Start Route" calls the same function. `running = true`, status `active`, agent + vehicle `active`, starts the GPS simulator. |
| `agentArrive(routeId, stopIndex)` | `POST /api/routes/{id}/stops/{index}/arrive` **A** [PICKUP_AGENT] | Stop → `ARRIVED`, return → `ARRIVED`, `AGENT_ARRIVED` event. |
| `agentPickup(routeId, stopIndex, counted)` | `POST /api/routes/{id}/stops/{index}/pickup` **A** [PICKUP_AGENT] | Body `{counted}`. Stop → `DONE`, next → `CURRENT`, return → `PICKED_UP` with `pickedQuantity`, `PICKED_UP` event, distributor notified. |

### 8.5 Manufacturer — `manufacturerService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `listInbox(manufacturerId)` | `GET /api/manufacturer/inbox` **A** [MANUFACTURER] | `FORWARDED` returns whose batch belongs to this manufacturer and is not `DESTROYED`, batch joined. |
| `scheduleFacility(batchIds, facilityId, date, actor)` | `POST /api/manufacturer/schedule` **A** [MANUFACTURER] | Body `{batchIds, facilityId, date}`. `FACILITY_SCHEDULED` event per batch. |
| `certEligibility(batch)` | `GET /api/batches/{id}/cert-eligibility` **A** [MANUFACTURER] | `{eligible, reason?}`. **Called during render today** — it is sync and pure in the mock. Keep the frontend computing it locally from the batch's `events[]`, and use this endpoint as the authoritative pre-check. The real enforcement is inside the upload endpoint regardless. |
| `uploadCertificate(batchId, {certId, fileName}, actor)` | `POST /api/manufacturer/certificates` **A** [MANUFACTURER] | Body `{batchId, certId, fileName}` (`multipart/form-data` once real PDFs land). Returns `{ok, batch, coveredBatches}` or `{ok: false, reason}`. |

### 8.6 Alerts and reports — `alertService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `listAlerts(filter)` | `GET /api/alerts?type=&status=&district=&drugCategory=&manufacturerId=` **A** | Role-scoped. **Server applies the category → severity → recency ordering** (§4.7). |
| `getAlert(id)` | `GET /api/alerts/{id}` **A** | Alert with `batch` joined. |
| `updateAlertStatus(id, status, officer)` | `PATCH /api/alerts/{id}/status` **A** [REGULATOR] | Body `{status, officer}`. Appends to `auditTrail`. |
| `listReports()` | `GET /api/reports` **A** [REGULATOR] | |
| `generateReport({…})` | `POST /api/reports` **A** [REGULATOR] | Body `{title?, region, category}`. |

### 8.7 Public — `verifyService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `verifyBatch(batchId)` | `GET /api/public/verify/{batchId}` **P** | Lookup by id, then code, then `BATCH-{input}`. Returns `{verdict, batch?, history?}`. Minimal fields only. Rate limit 30/min/IP. |
| `reportSuspicious({…})` | `POST /api/public/report` **P** | Body `{batchId?, location, notes, photoHash, pharmacyName}`. Creates a patient report + `PATIENT_REPORT` alert, notifies the regulator. Rate limit 5/min/IP. |

### 8.8 Reference — `referenceService.js`

| Service function | Endpoint |
| --- | --- |
| `getDistributors()` | `GET /api/reference/distributors` **A** |
| `getManufacturers()` | `GET /api/reference/manufacturers` **A** |
| `getFacilities()` | `GET /api/reference/facilities` **A** |
| `getPharmacies()` | `GET /api/reference/pharmacies` **A** |
| `getPharmacy(id)` | `GET /api/reference/pharmacies/{id}` **A** |
| `getSales(pharmacyId)` | `GET /api/sales?pharmacyId=` **A** |
| `getAgents(distributorId)` | `GET /api/reference/agents?distributorId=` **A** |
| `getVehicles(distributorId)` | `GET /api/reference/vehicles?distributorId=` **A** |

### 8.9 Entities — `entityService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `listEntities()` | `GET /api/entities` **A** [REGULATOR] | Pharmacies + distributors + manufacturers, each with `{score, risk, alertsOn, returnRate, disputeRate}`. Scoring formula in §4 of `entityService.js`: `100 - alerts*12 - disputeRate*0.4`, clamped 20–100; LOW ≥80, MEDIUM ≥55, else HIGH. |
| `getEntity(id)` | `GET /api/entities/{id}` **A** [REGULATOR] | Adds `alerts[]` and `batchCount`. |

### 8.10 Analytics — `analyticsService.js`

| Service function | Endpoint |
| --- | --- |
| `pharmacyStats(id)` | `GET /api/analytics/pharmacy/{id}/stats` **A** |
| `pharmacySparkline(id)` | `GET /api/analytics/pharmacy/{id}/sparkline` **A** |
| `pharmacyAnalytics(id)` | `GET /api/analytics/pharmacy/{id}` **A** |
| `distributorStats(id)` | `GET /api/analytics/distributor/{id}/stats` **A** |
| `distributorAnalytics(id)` | `GET /api/analytics/distributor/{id}` **A** |
| `manufacturerStats(id)` | `GET /api/analytics/manufacturer/{id}/stats` **A** |
| `manufacturerAnalytics(id)` | `GET /api/analytics/manufacturer/{id}` **A** |
| `regulatorStats()` | `GET /api/analytics/regulator/stats` **A** [REGULATOR] |
| `regulatorAnalytics()` | `GET /api/analytics/regulator` **A** [REGULATOR] |

Roughly half of the analytics payload is real aggregation over state and half is
deterministic synthetic data (`seededSeries`, hardcoded funnel, district compliance,
KPI constants). **Decision: hybrid.** Compute everything the database can answer
honestly — status counts, dispute counts, pending pickups, returns per week, top
drugs by volume, destroyed counts, alert counts. Keep a deterministic server-side
generator for long-horizon series that cannot exist in a freshly seeded database
(24-month destruction trend, 12-month national trend). Mark generated fields in the
response with `"synthetic": true` so nobody later mistakes a demo curve for a
measurement.

### 8.11 Notifications — `notificationService.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `getNotifications(role)` | `GET /api/notifications?role=` **A** | Scoped to the caller (§4.8). Max 40, newest first. |
| `markAllRead(role)` | `PATCH /api/notifications/read-all` **A** | |
| `markRead(role, id)` | `PATCH /api/notifications/{id}/read` **A** | |

### 8.12 Demo control — `db.js`

| Service function | Endpoint | Notes |
| --- | --- | --- |
| `resetDemo()` | `POST /api/demo/reset` **A** | Truncates and re-seeds. Gated by `ENABLE_DEMO_RESET`, off in production. Powers the profile-menu "Reset demo data" button. |
| `startSimulation()` | — | Becomes a server-side task; see §9.4. |

---

## 9. Real-time layer

Three things must be live: vehicle positions on five different maps, alerts landing
on the regulator dashboard within ~2 seconds, and notification bells across roles.

### 9.1 Transport

Native FastAPI WebSockets at `WS /api/ws?token=<access token>`. Redis pub/sub sits
behind it so any uvicorn worker can serve any subscriber.

Why not Server-Sent Events: SSE is one-directional and would still need a second
channel for subscribe/unsubscribe. Why not polling: the ~2-second re-entry alert is a
demo-critical requirement, and polling fast enough to meet it wastes far more than a
socket costs.

The token is validated on connect. An invalid or expired token is closed with 4401.
There is one exception to authentication: nothing. `/verify` is public but entirely
request/response — it opens no socket.

### 9.2 Channels and subscriptions

| Channel | Payload | Who subscribes |
| --- | --- | --- |
| `route:{routeId}` | position, ETA, stop transitions | distributor (owner), assigned agent, retailers with a return on that route, manufacturers with a batch on it, all regulators |
| `fleet:{distributorId}` | all that distributor's active vehicles | that distributor, all regulators |
| `fleet:all` | every active vehicle, nationally | regulators, manufacturers (filtered client-side) |
| `alerts:regulator` | every alert | all regulators |
| `alerts:manufacturer:{id}` | alerts on that manufacturer's batches | that manufacturer |
| `notifications:{role}:{entityId}` | notification objects | the matching user |
| `batch:{batchId}` | status change, new event | anyone currently viewing that batch |
| `returns:{distributorId}` | inbox changes | that distributor |

Subscriptions are **server-authorised**. The client sends
`{action: "subscribe", channel: "…"}` and the server checks the same RBAC matrix
from §6.5 before joining. A distributor cannot subscribe to another distributor's
fleet channel by asking nicely. Unauthorised subscribe returns
`{type: "error", code: "SUBSCRIBE_FORBIDDEN"}` and does not join.

### 9.3 Message shapes

```jsonc
// vehicle position — ~1/sec while a route is running
{ "type": "route.position", "channel": "route:route_1", "ts": "…",
  "data": { "routeId": "route_1", "pos": {"lat": 13.06, "lng": 80.23},
            "etaMin": 34, "vehicleReg": "TN 11 AB 1000", "agentName": "Ravi Kumar" } }

// stop transition — on agent action only
{ "type": "route.stop", "channel": "route:route_1", "ts": "…",
  "data": { "routeId": "route_1", "stopIndex": 2, "status": "DONE", "counted": 45 } }

// alert — the ~2s requirement
{ "type": "alert.created", "channel": "alerts:regulator", "ts": "…",
  "data": { /* the full alert object, same shape as GET /api/alerts */ } }

// notification — drives the bell badge
{ "type": "notification.created", "channel": "notifications:REGULATOR:reg_1", "ts": "…",
  "data": { "id": "ntf_…", "title": "…", "body": "…", "kind": "danger", "link": "…", "read": false } }

// batch change — refresh an open detail view
{ "type": "batch.updated", "channel": "batch:BATCH-DOX-2026-A17", "ts": "…",
  "data": { "batchId": "…", "status": "DESTROYED", "event": { /* new event */ } } }
```

Every message carries `type`, `channel`, `ts`, `data`. Clients dispatch on `type`.

### 9.4 How one agent's location reaches four maps at once

This is the fan-out the mock faked with shared `localStorage`, and it is the single
biggest change from mock to real.

```
gps_simulator (one asyncio task per active route, tick ~1s)
   │  advance seg_t, lerp position along route.path, recompute ETA
   │  persist to routes (throttled — every ~5th tick, not every tick)
   ▼
realtime.publish("route:{routeId}", {type: "route.position", …})
realtime.publish("fleet:{distributorId}", …)
realtime.publish("fleet:all", …)
   ▼
Redis pub/sub
   ▼
every uvicorn worker holding a matching subscriber
   ▼
   ├─► Distributor  — /distributor/pickups/{routeId}, /distributor/fleet
   ├─► Pickup agent — /agent/today (own route)
   ├─► Retailer     — /pharmacy/returns/{id}/track (their stop on that route)
   ├─► Manufacturer — /manufacturer/fleet-map (batches they own)
   └─► Regulator    — /regulator/fleet-map (everything)
```

Publish once per channel, not once per subscriber. Redis handles the multiplication.

Position writes are throttled deliberately: at 1 tick/second across several routes,
persisting every tick is pure write amplification for data that is only interesting
live. Publish every tick, persist every fifth. On restart the vehicle resumes from
the last persisted point, which is within five seconds of truth.

### 9.5 Frontend integration

The `useLive(selector)` hook in `hooks/useDb.js` is the seam. It currently
subscribes to the in-memory store. It gets rewritten once to subscribe to a
WebSocket-backed client store, and **every component that uses it keeps working
untouched** — the maps, the notification bell, the agent route view, the fleet
tables. That is the payoff of the existing architecture, and it is why rule 3 exists.

`useQuery` call sites stay as they are; the WebSocket triggers targeted
`queryClient.invalidateQueries` for the affected keys.

### 9.6 Reconnection

- Client: exponential backoff — 1s, 2s, 4s, 8s, capped at 30s, with jitter.
- On reconnect, the client re-subscribes to its channels and **refetches** the
  relevant queries rather than trying to replay missed messages. State is small;
  refetching is simpler and cannot desync.
- Heartbeat ping every 30s; a client that misses two pongs is dropped.
- While disconnected the UI shows a subtle "reconnecting" indicator. It never blocks
  interaction — a pharmacy must still be able to work through a flaky connection.
- Messages are **not** queued for offline clients. A dropped position update is
  worthless three minutes later, and alerts are refetched on reconnect anyway.

---

## 10. Error handling

One error envelope everywhere:

```json
{ "error": { "code": "CHAIN_HALTED_DISPUTE",
             "message": "Quantity dispute unresolved. Chain halted.",
             "details": { "returnId": "ret_1", "claimed": 50, "received": 45 } } }
```

| HTTP | When | Example codes |
| --- | --- | --- |
| 400 | malformed request | `MALFORMED_REQUEST` |
| 401 | missing / expired token | `TOKEN_EXPIRED`, `INVALID_CREDENTIALS` |
| 403 | wrong role, or not your resource | `FORBIDDEN_ROLE`, `NOT_YOUR_BATCH`, `NOT_YOUR_RETURN` |
| 404 | not found | `BATCH_NOT_FOUND`, `RETURN_NOT_FOUND` |
| 409 | **domain rule violation** | `CHAIN_HALTED_DISPUTE`, `NOT_DISTRIBUTOR_CONFIRMED`, `NOT_FORWARDED`, `ALREADY_DESTROYED`, `BATCH_DESTROYED_REENTRY`, `INSUFFICIENT_STOCK`, `INVALID_STATUS_TRANSITION` |
| 422 | validation failure | `RESOLUTION_NOTES_REQUIRED`, `QUANTITY_OUT_OF_RANGE` |
| 429 | rate limited | `RATE_LIMITED` |
| 500 | unexpected | `INTERNAL_ERROR` (never leaks a stack trace to the client) |

409 is reserved for domain-rule violations specifically. That separation lets the
frontend distinguish "you typed something wrong" (422, fix the field) from "the
system is refusing this on principle" (409, show the rule) — which is exactly the
difference between the certificate-blocked banner and a form validation message.

`DomainError` subclasses in `core/errors.py` map to these codes through a single
exception handler. A service raises a domain error; it never constructs an
`HTTPException`. Every 5xx is logged with the request id, the user id, and the
operation — and never with a password, token, or private key.
