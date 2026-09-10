# BUILDPHASES — The order we build in

Ordered so the app is demoable at the end of every phase. Read `ARCHITECTURE.md`
first — this document assumes its data model, API contract, and rule definitions.

The ordering principle: **the five never-cut capabilities land as early as their
dependencies allow.** Re-entry detection and Patient Shield come before the return
flow, because they only need batches and a pre-destroyed seed record, and getting
them working early removes the risk of them arriving half-finished on the last day.

---

## The demo path — the acceptance test for everything

Every phase is measured against this. It must work end to end when the build is
done, and each phase states how much of it is live at that point.

1. Pharmacy → Add Stock → scan `BATCH-DOX-2026-A17` (Doxorubicin) → register 50 units
2. Batch is `EXPIRING_SOON` → Start Return → photo → confirm 50 → select distributor
3. Distributor → the return appears in Inbox as **NEW**
4. Distributor → create route → assign agent + vehicle → Dispatch → vehicle moves on the map
5. Pickup Agent → Start Route → arrive at stop → enter **45** → Pickup complete
6. Distributor → **dispute gate fires**, chain halted → resolution notes → Forward
7. Manufacturer → Schedule facility → Upload certificate (blocked until distributor-confirmed) → batch flips to `DESTROYED`
8. Any pharmacy → scan `BATCH-DOX-2026-B04` (pre-destroyed) → **re-entry alert fires on the Regulator dashboard within ~2s**
9. Public `/verify` → scan `BATCH-DOX-2026-B04` → 🔴 **DO NOT USE**

Demo codes: `BATCH-DOX-2026-A17` (active), `BATCH-DOX-2026-B04` (destroyed),
`BATCH-FAKE-9999-Z01` (not found / counterfeit).

---

## Phase 0 — Foundation

**Build**

- Replace `backend/server.py` with the `app/` package from `ARCHITECTURE.md` §2.
- `config.py` with pydantic-settings; `.env.example` listing every variable.
- Async SQLAlchemy engine + session dependency; Alembic initialised.
- `core/errors.py`: the `DomainError` hierarchy and the single exception handler
  producing the §10 envelope.
- CORS with an explicit origin allowlist (delete `allow_origins=["*"]`).
- Structured logging with a request id per request.
- `GET /api/health` returning `{status, service, db, version}` — now with a real
  database round-trip.
- pytest + httpx `AsyncClient` harness, and a CI-less `make test` that runs green.

**Unblocks:** everything. No feature can be built on the stub.

**Verify:** `GET /api/health` reports `db: "ok"`. A deliberate exception returns the
structured envelope, not a stack trace. `alembic upgrade head` builds an empty
schema from scratch. Frontend still runs untouched on mocks.

---

## Phase 1 — Auth, entities, seed

**Status: COMPLETE (2026-09-10).** Backend now has real auth and real
reference data. Summary below; implementation detail lives in
`ARCHITECTURE.md` §6, §"Phase 1 implementation notes".

- **Implemented:** `users`, `refresh_tokens`, `pharmacies`, `distributors`,
  `manufacturers`, `facilities`, `regulators`, `agents`, `vehicles`, `drugs`
  (migration `0001_phase1_auth_entities`); Argon2 password hashing; JWT
  access + refresh with hashed-at-rest refresh tokens and rotation
  (reuse of a rotated token revokes its whole family); `POST
  /api/auth/{login,demo-login,refresh,logout}`, `GET /api/auth/me`; the five
  demo accounts as real seeded users going through the same token-issuance
  code path as a normal login; `core/rbac.py` (the role → permission matrix)
  plus `deps.get_current_user` / `deps.require_role` guards; `GET
  /api/reference/{distributors,manufacturers,facilities,pharmacies,
  pharmacies/{id},agents,vehicles,drugs}`; `GET /api/regulator/profile`
  (REGULATOR-only — moves the officer profile out of `regulator.jsx`'s
  hardcoded Profile card, per ARCHITECTURE.md §4.2 open question #5); `POST
  /api/demo/reset`; Ed25519 keypair generated and encrypted at rest for
  every seeded user (signing/verification itself is Phase 2).
- **Verified:** `alembic upgrade head` runs clean from an empty database
  (both `dot` and `dot_test`) and from an existing Phase 0 schema. 53/53
  tests pass (`pytest -q`), covering login success/failure, password-hash
  and signing-key exclusion from every response, `/me` with a valid/
  missing/garbage/expired token, all five demo logins through the real
  login code path with real Argon2-backed rows, demo-login 404 when
  `ENABLE_DEMO_LOGIN=false`, refresh rotation, rotated-token reuse revoking
  the whole family, logout revocation and idempotency, a RETAILER token
  getting 403 on the regulator-only endpoint (and every other non-REGULATOR
  role too), unauthenticated requests getting 401, seeded entity counts
  and critical identities (`dist_1`, `agent_1`, `mfr_1`, `reg_1`, `ph_1`),
  and two consecutive resets producing logically identical rows (ids,
  names, roles, relationships — Argon2 salts and Ed25519 keys legitimately
  differ each run).
- **Known limitations / deviations:** password hashing uses `argon2-cffi`
  directly instead of the `passlib` wrapper ARCHITECTURE.md §1.4 named
  (passlib's argon2 backend is broken against current argon2-cffi releases;
  same algorithm, no functional change). `entity_id` on `users` has no
  database FK (it targets whichever entity table matches `role`, which
  Postgres cannot express as one FK) — documented in `models/user.py`,
  enforced only at seed time. Agent/vehicle counts follow this document's
  seed-data-spec table (7 agents, 5 vehicles) rather than the frontend
  `seed.js` script's actual runtime output (10 agents, 7 vehicles) — the
  critical identities (`agent_1`/`dist_1`) match either way. `GET
  /api/reference/drugs` is additive (not in ARCHITECTURE.md §8.8's table)
  since `drugs` is Phase-1-owned reference data later phases will need.

**Build**

- Migrations for `users`, `pharmacies`, `distributors`, `manufacturers`,
  `facilities`, `regulators`, `agents`, `vehicles`, `drugs`.
- `seed_data.py` — a faithful port of `frontend/src/services/seed.js` (see
  [Seed data spec](#seed-data-spec)).
- Argon2 hashing, JWT access + refresh, rotation, revocation table.
- `POST /api/auth/login`, `/demo-login`, `/refresh`, `/logout`, `GET /api/auth/me`.
- Ed25519 keypair generated per entity at seed time.
- `core/rbac.py` — the role → permission matrix, plus the role-guard dependency.
- Reference endpoints (§8.8) — the first real data the frontend can read.
- `POST /api/demo/reset`.

**Unblocks:** every authenticated endpoint. Nothing else can be scoped without a
user.

**Verify:** all five demo logins return valid tokens through the real login code
path. A RETAILER token on a regulator-only endpoint returns 403. An expired token
returns 401. `demo-login` returns 404 when `ENABLE_DEMO_LOGIN=false`. Reset re-seeds
to an identical state (compare a hash of the seeded rows).

**Demoable:** log in as any of the five roles against the real backend; the dropdowns
that list distributors, facilities, agents and vehicles are reading from Postgres.

---

## Phase 2 — Batches and the hash-chained event log

**Status: COMPLETE (2026-09-15).** Backend now has a real batch ledger and
a genuinely tamper-evident, append-only event log. Summary below;
implementation detail lives in `ARCHITECTURE.md`'s Phase 2 implementation
notes (after §7.5).

- **Implemented:** `batches`, `events` (with all three `UNIQUE` chain-
  integrity constraints), `sales` (migration `0002_phase2_batches_events_sales`,
  also adds a signing keypair column pair to `pharmacies`/`distributors`/
  `manufacturers`/`agents` — see below); `core/crypto.py` canonical JSON +
  SHA-256 + Ed25519 sign/verify; `event_service.py` as the single writer to
  `events`, row-lock-safe append and read-only `verify_chain`;
  `batch_service.py` (list/get/search/register/sale/verify-chain, with
  role-scoped reads); `GET /api/batches`, `GET /api/batches/{id}` (id or
  code), `GET /api/search`, `POST /api/batches`, `POST
  /api/batches/{id}/sale`, `GET /api/batches/{id}/verify-chain`
  (REGULATOR-only); status derivation (`ACTIVE`/`EXPIRING_SOON`/`EXPIRED`)
  computed on every read against the pinned `DEMO_NOW`, no scheduler; ~44
  seeded batches with complete, genuinely-signed event histories
  (`app/seed/seed_batches.py`), including both hero batches and the
  confirmed absence of `BATCH-FAKE-9999-Z01`.
- **Verified:** `alembic upgrade head` runs clean from an empty database
  and incrementally from the Phase 1 schema (both directions — downgrade
  to base and back up were exercised). 106/106 tests pass (`pytest -q`;
  full suite including Phase 0 and Phase 1). Registering a batch commits a
  `Batch` row and its `REGISTERED` event atomically; recording a sale
  decrements quantity, inserts a `Sale` row, and appends a `SALE` event
  atomically, and rejects a sale that would take quantity negative
  (`409 INSUFFICIENT_STOCK`) including at the exact boundary. All 44 seeded
  batches' chains verify (`valid: true`), including the 8-event `B04`
  chain. Tamper detection: a directly-modified `hash`, `meta`, `prev_hash`,
  or `signature` is each independently caught, a removed event is caught
  as a sequence gap, and verification never rewrites the row it just
  flagged. Fork rejection: duplicate `(batch_id, sequence)`, duplicate
  `hash`, and duplicate `(batch_id, prev_hash)` are all rejected by the
  real PostgreSQL constraints (`IntegrityError`), with a correctly-chained
  insert accepted as a control. Concurrency: 10 concurrent `POST
  .../sale` requests against one batch, each opening its own database
  connection, produce exactly 11 events (1 `REGISTERED` + 10 `SALE`) with
  sequence `0..10`, no duplicate, no gap, and a chain that still verifies.
  Determinism: two consecutive resets reproduce byte-identical event
  hashes for all 44 batches (signatures legitimately differ — each reset
  generates a fresh Ed25519 keypair per entity).
- **Known limitations / deviations:** event actors are entities (a
  pharmacy, a distributor, an agent, a manufacturer), not login users —
  matching how the frontend already constructs `actor` (entity id, not
  user id) — so the Ed25519 signing keypair Phase 2 actually uses lives on
  `pharmacies`/`distributors`/`manufacturers`/`agents`, not on `users`
  where Phase 1 first put it. Phase 1's `users.signing_*` columns are now
  vestigial (harmless, unused by event signing). The new entity signing-key
  columns are nullable at the database level (no backfill migration for
  pre-Phase-2 rows); every seed path populates them. A duplicate batch id
  at registration is rejected outright regardless of the existing batch's
  status — Phase 3 changes only the `DESTROYED` branch of that check to
  fire a re-entry alert instead, everything else in `register_batch` is
  unchanged. Role-based batch-list scoping for `DISTRIBUTOR` and
  `PICKUP_AGENT` is an interim proxy (`distributor_id` match; empty list,
  respectively) until routes/returns exist in Phases 4-5 to scope by. The
  full test suite takes several minutes because most tests re-run the real
  44-batch/~540-event seed; acceptable for now, worth revisiting if it
  becomes a workflow problem.

**Build**

- Migrations for `batches`, `events`, `sales` — including the three uniqueness
  constraints on `events` that make forking impossible.
- `core/crypto.py`: canonical JSON, SHA-256 chaining, Ed25519 sign/verify.
- `event_service.py` — the single writer to the events table, with a batch row lock
  during append.
- `GET /api/batches`, `GET /api/batches/{id}` (id **or** code), `GET /api/search`.
- `POST /api/batches` (registration, without fraud checks yet),
  `POST /api/batches/{id}/sale`.
- `GET /api/batches/{id}/verify-chain`.
- Daily status recomputation (`ACTIVE` → `EXPIRING_SOON` → `EXPIRED`) plus derive
  on read.

**Unblocks:** returns, fraud detection, certificates, the regulator audit trail —
all of them read or append events.

**Verify:** the hash-chain test suite from `ARCHITECTURE.md` §7.5 — tamper detection,
gap detection, fork rejection, 10 concurrent appends with no duplicate sequence.
Registering a batch appends `REGISTERED`. Selling decrements quantity and appends
`SALE`. Chain verification on every seeded batch returns valid.

**Demoable:** pharmacy inventory, batch detail with the real hash-chain timeline,
⌘K search, and the regulator's audit trail — all on live data.

---

## Phase 3 — Fraud engine, alerts, Patient Shield

Two never-cut capabilities land here, as early as their dependencies allow.

**Status: COMPLETE (2026-09-16).** Re-entry detection and Patient Shield
are both live and demo-path steps 8 and 9 work end to end against the real
backend. Summary below; implementation detail lives in ARCHITECTURE.md's
§7.5.2 "Phase 3 implementation notes".

- **Implemented:** `alerts`, `patient_reports` (migration
  `0003_phase3_fraud_alerts`); `fraud_service.py` (`check_reentry`,
  `check_quantity_cap`); `alert_service.py` (raise/list/get/update-status,
  with the category → severity → recency ordering from §4.7 applied
  server-side); `verify_service.py` (public verify + suspicious report);
  re-entry wired into `POST /api/batches` (the `DESTROYED` branch of the
  existing duplicate-id check) and `POST /api/batches/{id}/sale` (a new
  check after ownership, before the stock check); `GET /api/alerts`, `GET
  /api/alerts/{id}` (batch joined, events included), `PATCH
  /api/alerts/{id}/status` (REGULATOR-only); the public router —`GET
  /api/public/verify/{batchId}`, `POST /api/public/report` — carrying no
  auth dependency anywhere, ever; `slowapi`-backed rate limiting on both
  public routes (default 30/min verify, 5/min report, both configurable);
  `QUANTITY_CAP` added to the regulator alert type filter
  (`pages/regulator.jsx`) — additive, no screen redesign, per rule 3.
- **Verified:** 147/147 tests pass (`pytest -q`; full suite including
  Phases 0-2). Registering `BATCH-DOX-2026-B04` returns `409
  BATCH_DESTROYED_REENTRY` with a critical `REENTRY` alert in the response
  body, appends a `REENTRY_BLOCKED` event, and leaves the batch's quantity
  and status untouched; repeated attempts each raise their own alert; a
  duplicate id on a non-destroyed batch is still the Phase 2 flat 409
  (unchanged). Attempting a sale on a batch a pharmacy still owns after it
  was destroyed is refused the same way; a non-owner's sale attempt is
  still 403 before any re-entry check runs (no alert leaks to a
  non-owner). `/api/public/verify/{batchId}` returns `GENUINE` for A17,
  `DESTROYED` (with `certId`, `destroyedDate`, and the last 5 events) for
  B04, and `NOT_FOUND` for both a deliberately-absent id and an arbitrary
  string, by id, by bare code, and via the `BATCH-` fallback — all with
  zero credentials, and a route-table-driven test asserts every current
  and future `/api/public/*` route stays non-401 with no auth header.
  Public verification of a destroyed batch does not raise a `REENTRY`
  alert; a follow-up suspicious report does raise `PATIENT_REPORT`, at
  `critical` severity when the reported batch is destroyed and `high`
  otherwise. Alert RBAC scoping matches §6.5 exactly (RETAILER/DISTRIBUTOR
  by own `entityId`, MANUFACTURER by own `manufacturerId`, REGULATOR sees
  all, PICKUP_AGENT gets 403), alert ordering matches the documented
  category → severity → recency priority, and `PATCH
  /api/alerts/{id}/status` is REGULATOR-only and appends a real audit-trail
  entry. The quantity-cap rule itself (arithmetic, severity by category,
  sold units still counting, destroyed batches excluded) is verified
  directly at the service layer.
- **Known limitations / deviations:** the quantity-cap check is wired into
  `register_batch` but is structurally unreachable-as-a-breach under the
  current schema — see ARCHITECTURE.md §7.5.2 for the full reasoning
  (short version: the duplicate-id gate that Phase 2 already locked in
  refuses the second registration §7.4's own worked example depends on,
  before this rule could ever see a genuinely additional incoming
  quantity). The rule is correct and independently tested
  (`tests/test_quantity_cap.py`), not a stub — it has no live trigger path
  today, which is a schema property, not an implementation gap. No alerts
  are seeded (`QUANTITY_MISMATCH`/`CERT_MISMATCH` depend on Phases 4/6);
  `POST /api/demo/reset` truncates `alerts`/`patient_reports` to empty
  rather than fabricating a re-entry incident with no corresponding seeded
  attempt. `BatchOut.from_model` and batch status derivation
  (`app/services/batch_status.py`) were extracted out of `batch_service`
  during this phase, purely to give `alert_service` a batch-join it could
  use without importing `batch_service` and creating a circular import
  through `fraud_service` — a refactor, not a behavior change (all 106
  pre-existing tests still pass unmodified). Notification fan-out
  (`notification_service.notify(...)` in ARCHITECTURE.md's §7.3 pseudocode)
  and WebSocket publish are not implemented — that infrastructure doesn't
  exist until Phases 7-8, so this phase's alerts reach the regulator on
  refetch only, exactly as BUILDPHASES.md already anticipated for this
  phase ("the alert reaches the regulator dashboard on refetch rather than
  in ~2 seconds").

**Build**

- Migrations for `alerts`, `patient_reports`.
- `fraud_service.py`: re-entry detection (§7.3) and the quantity-cap check (§7.4).
- Wire re-entry into `POST /api/batches` and `POST /api/batches/{id}/sale`.
- `alert_service.py` with the category → severity → recency ordering.
- Alert endpoints (§8.6) including regulator status transitions and audit trail.
- **Public router**: `GET /api/public/verify/{batchId}`, `POST /api/public/report`.
- Rate limiting on the public routes.
- The test that fails the build if any `/api/public/*` route acquires an auth
  dependency.
- Add `QUANTITY_CAP` to the frontend `STATUS_MAP` and the regulator type filter
  (additive — no screen redesign).

**Unblocks:** the regulator dashboard's reason for existing.

**Verify:** the full test lists in §7.3 and §7.4. Registering `BATCH-DOX-2026-B04`
returns 409 with a critical alert and appends `REENTRY_BLOCKED`. `/verify` on
B04 returns `DESTROYED`, on A17 returns `GENUINE`, on `BATCH-FAKE-9999-Z01` returns
`NOT_FOUND` — all with no credentials at all.

**Demoable:** demo steps **8 and 9** work — though the alert reaches the regulator
dashboard on refetch rather than in ~2 seconds. The push timing lands in Phase 7.

---

## Phase 4 — Return flow and the dispute gate

**Status: COMPLETE (2026-09-17).** The return flow and the dispute gate
are both live; the last three of the five never-cut capabilities to land
are this phase's dispute gate plus (partially) the return flow itself —
certificate binding and the physical pickup chain still wait on Phases 5-6.
Summary below; implementation detail lives in ARCHITECTURE.md's §7.1.1
"Phase 4 implementation notes".

- **Implemented:** `returns`, `notifications` (migration
  `0004_phase4_returns`); `return_service.py` (list/get with §6.5 role
  scoping, create, distributor receive, resolve, forward, Kanban
  `set_return_status`); the shared `assert_not_disputed` guard, written so
  a later phase's certificate binding (§7.2) can import it unchanged;
  `notification_service.py` (write-only — `notify()`, matching
  `notificationService.js`'s `notify(role, title, body, kind, link)`
  signature exactly; read endpoints are Phase 8's job); all seven `/api/returns*`
  endpoints from §8.3, including the Kanban `PATCH /api/returns/{id}/status`
  with genuine forward-only transition validation (REQUESTED → SCHEDULED →
  PICKED_UP → CONFIRMED; no skip, no reverse, no move out of `DISPUTED`) —
  a real hardening over the mock, which validates none of this client-side
  drag-and-drop. `fraud_service.check_reentry` and `alert_service.raise_alert`
  are reused for return-side re-entry and the `QUANTITY_MISMATCH` alert
  rather than reimplemented; `alert_service.update_status` was refactored
  to stop committing internally (now a shared `transition()` helper) so
  `resolve_dispute` can close the mismatch alert inside its own single
  atomic transaction — the PATCH `/api/alerts/{id}/status` route now owns
  that commit instead.
- **Verified:** 191/191 tests pass (`pytest -q`; full suite, Phases 0-4),
  44 of them new to this phase. The three quantity attestations
  (`quantityClaimed`, `pickedQuantity`, `quantityReceived`) are confirmed
  independent end to end — nothing auto-copies one into another anywhere
  in the codebase, and a dedicated test asserts this directly. A matching
  receive confirms with no alert; a mismatch produces `DISPUTED`, exactly
  one `QUANTITY_MISMATCH` alert, and — matching the mock and
  ARCHITECTURE.md §7.1 exactly — no batch event and no holder change (the
  batch stays pharmacy-held until confirmation, disputed or resolved).
  Calling `forward` directly on a disputed return with a valid distributor
  token, no UI involved, returns `409 CHAIN_HALTED_DISPUTE` with the exact
  message `"Quantity dispute unresolved. Chain halted."` — the required
  direct-bypass proof. Blank and whitespace-only resolution notes are both
  `422 RESOLUTION_NOTES_REQUIRED`; a valid resolution flips the return to
  `CONFIRMED`, appends `DISPUTE_RESOLVED`, closes the alert with a
  `RESOLVED_AT_DISTRIBUTOR` audit-trail entry carrying the resolution
  notes, and genuinely reopens forwarding (asserted by actually forwarding
  it afterward, not just checking the status field). Forwarding a
  never-received (`REQUESTED`) return directly is `409
  RETURN_NOT_CONFIRMED` — never trusts a client-supplied status. Ten
  state-machine bypass scenarios are each tested directly: forward-while-
  REQUESTED, forward-while-DISPUTED, resolve-while-not-DISPUTED,
  receive-on-FORWARDED, repeat-receive-after-CONFIRMED, Kanban stage-skip,
  Kanban backwards move, Kanban move-out-of-DISPUTED, an unowned/foreign
  return silently skipped on forward (not leaked), and a garbage status
  string on the Kanban endpoint. Two concurrent `receive` calls with
  different quantities against the same return resolve to exactly one
  200 and one `409 RETURN_NOT_RECEIVABLE` — real PostgreSQL row locking
  (`return_repo.get_for_update`) serializes them, at most one
  `DISTRIBUTOR_CONFIRMED` event is ever appended, and the batch's chain
  still verifies afterward. A full create → dispute → resolve → forward
  run leaves exactly four events (`REGISTERED`, `RETURN_INITIATED`,
  `DISPUTE_RESOLVED`, `FORWARDED`) and `verify-chain` reports `valid:
  true`. `alembic downgrade -1` then `upgrade head` was exercised on the
  test database. The full create → inbox → dispute → resolve → forward
  path was additionally run against a live `uvicorn` server (not only
  pytest) with real HTTP calls and a real database, confirming demo steps
  1, 2, 3, and 6.
- **Known limitations / deviations:** ARCHITECTURE.md §7.1's pseudocode
  gates `receive` on `status in (SCHEDULED, ARRIVED, PICKED_UP)` — statuses
  only reachable once Phase 5's pickup pipeline exists to advance a return
  past `REQUESTED`. Since Phase 4 explicitly does not implement pickups,
  `REQUESTED` was added to the receivable set as a deliberate interim
  adaptation (documented in ARCHITECTURE.md §7.1.1) — without it, a return
  created in this phase could never be received at all, and demo step 6
  would be unreachable. `route_id` is a plain nullable `TEXT` column with
  no foreign key (`routes` doesn't exist until Phase 5's migration creates
  it); Phase 5 adds the constraint once the target table exists. No
  alerts/notifications are seeded on reset — both tables truncate to empty,
  same as Phase 3's `alerts`/`patient_reports` — a demo session gets its
  first return-flow notification live. `dispute_notes` exists as a schema
  column (ARCHITECTURE.md §4.5) but no Phase 4 endpoint ever sets it — the
  mock never populates it either, and no documented flow explains what
  would. `forward_returns` treats "not found" and "not this distributor's"
  the same way (silently skipped, not leaked) but raises immediately for
  any state-machine violation (`DISPUTED`, not yet `CONFIRMED`) rather than
  silently skipping those too — a deliberate reading of ARCHITECTURE.md
  §8.3's "the API reports them instead" against this phase's explicit,
  repeated requirement that illegal transitions get hard, direct 409s, not
  soft skip-array entries; see ARCHITECTURE.md §7.1.1 for the full
  reasoning.

**Build**

- Migration for `returns` with all three quantity columns.
- `return_service.py`: create, receive, resolve, forward, Kanban status transitions.
- The dispute gate (§7.1) and the shared `assert_not_disputed` guard.
- Return status state-machine validation, including rejecting any move out of
  `DISPUTED`.
- Return endpoints (§8.3).
- Notification records on every state change.

**Unblocks:** pickups (routes consume `REQUESTED` returns) and the manufacturer inbox
(which consumes `FORWARDED` ones).

**Verify:** the dispute-gate test list in §7.1 — including calling `forward`
directly with a valid token on a `DISPUTED` return and getting 409. Two concurrent
receive calls produce one outcome and a clean chain.

**Demoable:** demo steps **1, 2, 3 and 6** — a return is created, appears in the
distributor inbox, and the dispute gate halts the chain until notes are filed.

---

## Phase 5 — Pickups, routes, and the agent app

**Build**

- Migrations for `routes`, `route_stops`.
- `pickup_service.py`: route creation with nearest-neighbour ordering (and respect
  for `manualOrder`), dispatch, agent arrive, agent pickup.
- Pickup endpoints (§8.4), including positional `stopIndex` addressing.
- `gps_simulator.py` as an asyncio task: advances position along `path`, throttled
  persistence, no stop-status mutation.
- Agent-scoped RBAC — an agent may only act on their own assigned route.

**Unblocks:** the full physical chain of custody, and the real-time layer's primary
data source.

**Verify:** creating a route sets its returns to `SCHEDULED`. Dispatch flips
`running`, `status`, agent and vehicle. Arrive and pickup append the right events and
set `picked_quantity`. Agent B cannot act on agent A's route (403). The simulator
moves a vehicle and never marks a stop `DONE` by itself.

**Demoable:** demo steps **4 and 5** — dispatch, a moving vehicle (position polled
until Phase 7), arrival, and a counted pickup of 45 against a claimed 50, which then
trips the Phase 4 dispute gate.

---

## Phase 6 — Manufacturer and certificate binding

The last never-cut capability, and the phase that completes the demo path.

**Build**

- `manufacturer_service.py`: inbox, facility scheduling, certificate binding (§7.2).
- Manufacturer endpoints (§8.5) including `cert-eligibility`.
- Certificate upload flipping the batch to `DESTROYED`, with `cert_id` unique at the
  database level.
- Notifications to regulator and retailer on destruction.

**Unblocks:** the destroyed state that re-entry detection and Patient Shield depend
on for *newly* destroyed batches — closing the loop end to end rather than relying on
the pre-seeded B04.

**Verify:** the certificate-binding test list in §7.2 — blocked before confirmation,
blocked before forwarding, blocked when disputed, blocked when already destroyed,
403 for another manufacturer, exactly one `DESTROYED` event on a double submit.

**Demoable:** **the entire 9-step demo path**, end to end, on a real backend. Step 8
still arrives by refetch rather than push.

---

## Phase 7 — Real-time

**Build**

- Redis, `core/realtime.py`: publisher, connection registry, channel authorisation
  reusing the §6.5 matrix.
- `WS /api/ws` with token auth on connect and server-authorised subscriptions.
- Publish on: alert created, batch updated, route position, stop transition,
  notification created — always **after** commit.
- Rewrite `hooks/useDb.js` `useLive` to read from a WebSocket-backed client store.
- Reconnection with backoff, heartbeat, and refetch-on-reconnect.

**Unblocks:** the ~2-second alert requirement and genuinely live maps across roles.

**Verify:** open a regulator client, register B04 from a pharmacy client, assert the
alert arrives in **under 2 seconds**. One moving agent updates the distributor,
retailer, manufacturer and regulator maps simultaneously. A distributor's subscribe
attempt on another distributor's fleet channel is rejected. Kill the socket
mid-route; the client reconnects and resyncs.

**Demoable:** the demo path in full, at full speed, exactly as specified.

---

## Phase 8 — Analytics, entities, notifications, reports

**Build**

- `analytics_service.py` — the hybrid model from §8.10, with `synthetic: true`
  marking generated series.
- All nine analytics endpoints.
- `entity_service.py` — compliance scoring, ported formula.
- Notification endpoints with server-side scoping.
- Report listing and generation (metadata; PDF rendering is Phase 9).

**Unblocks:** the four analytics pages and the regulator's entities view.

**Verify:** every KPI that claims to be real is reproducible from a SQL query.
Entity scores match the frontend's formula on identical inputs. One pharmacy cannot
see another's notifications.

**Demoable:** all six interfaces fully live. No mock code path remains.

---

## Phase 9 — Hardening and operations

Not required for the demo. Documented so it is a decision, not an oversight.

**Build**

- `Dockerfile` + `docker-compose.yml` (api, postgres, redis).
- CI: lint, migrate, test on push.
- Real PDF generation for certificates and CDSCO reports; object storage for uploads.
- Real photo upload with server-computed `photo_hash`.
- Rate limiting on all authenticated endpoints, not only public ones.
- Metrics, error tracking, DB backups, key rotation runbook.
- Load test on the WebSocket fan-out.

---

## Frontend swap plan

The frontend does not change shape. Only the bodies of service functions change,
plus one new HTTP client, one auth store change, and one hook rewrite.

### Files that change

| File | Change | Phase |
| --- | --- | --- |
| `src/lib/api.js` | **New.** `fetch` wrapper: base URL, bearer header, refresh-on-401 with a single-flight retry, error-envelope unwrapping. | 1 |
| `src/store/authStore.js` | `login` calls `POST /api/auth/login`; store tokens; merge `label`/`home`/`color` from the existing role map; keep `DEMO_ACCOUNTS` for the one-click buttons, now calling `/demo-login`. | 1 |
| `src/services/referenceService.js` | Bodies → `fetch`. | 1 |
| `src/services/batchService.js` | Bodies → `fetch`. `appendEvent` deleted — the server owns it. `computeStatus` stays as a display helper. | 2 |
| `src/services/verifyService.js` | Bodies → `fetch` against `/api/public/*`. **No auth header.** | 3 |
| `src/services/alertService.js` | Bodies → `fetch`. `pushAlert` deleted — server-side only. | 3 |
| `src/services/returnService.js` | Bodies → `fetch`. | 4 |
| `src/services/pickupService.js` | Bodies → `fetch`. | 5 |
| `src/services/manufacturerService.js` | Bodies → `fetch`. `certEligibility` stays a local pure function over `batch.events` (it is called during render); the server enforces the rule regardless. | 6 |
| `src/services/db.js` | `startSimulation` deleted. `resetDemo` → `POST /api/demo/reset`. Local store becomes a WebSocket-fed cache. | 7 |
| `src/hooks/useDb.js` | `useLive` subscribes to the WebSocket store instead of the local one. **No consuming component changes.** | 7 |
| `src/services/notificationService.js` | Bodies → `fetch`. `startNotificationSim` deleted. | 8 |
| `src/services/analyticsService.js` | Bodies → `fetch`. | 8 |
| `src/services/entityService.js` | Bodies → `fetch`. | 8 |
| `src/services/seed.js` | Deleted once Phase 8 lands. Keep it until then so mock mode still runs. | 8 |
| `src/components/common/index.jsx` | Add a `QUANTITY_CAP` entry to `STATUS_MAP`. Additive only. | 3 |

**No page component changes.** If a `pages/*.jsx` file needs editing to accommodate
the backend, stop — that is rule 3 in `CLAUDE.md` being violated, and the endpoint is
what should change.

### Environment variables

Frontend (`frontend/.env`):

```
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/api/ws
```

The current value points at a dead Emergent preview URL and is read by nothing —
replace it.

Backend (`backend/.env`):

```
DATABASE_URL=postgresql+asyncpg://dot:dot@localhost:5432/dot
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=<generated, never committed>
JWT_ACCESS_TTL_MIN=30
JWT_REFRESH_TTL_DAYS=7
SIGNING_MASTER_KEY=<generated, never committed>
CORS_ORIGINS=http://localhost:3000
DEMO_NOW=2026-09-15T09:30:00+05:30
ENABLE_DEMO_LOGIN=true
DEMO_PASSWORD=<demo only>
ENABLE_DEMO_RESET=true
PUBLIC_VERIFY_RATE_LIMIT=30/minute
PUBLIC_REPORT_RATE_LIMIT=5/minute
```

`MONGO_URL` and `DB_NAME` are removed — nothing ever read them.

### CORS

Explicit allowlist from `CORS_ORIGINS`, `allow_credentials=true`, methods
`GET, POST, PATCH, DELETE, OPTIONS`, headers `Authorization, Content-Type`. Never
`*` — it is incompatible with credentialed requests and is a real vulnerability once
tokens exist. The WebSocket endpoint validates `Origin` on upgrade.

### Error conventions on the client

`api.js` unwraps the §10 envelope and throws an `ApiError` carrying `code`,
`message`, `details`, `status`. Then:

- **409** → show `error.message` directly. These are domain rules, and their messages
  are already written for humans ("Quantity dispute unresolved. Chain halted.", "This
  batch has not been confirmed at the distributor stage."). The existing `toast.error`
  and blocked-banner call sites already render exactly this kind of string.
- **422** → map `details.field` to the form field.
- **401** → attempt one refresh; on failure, clear auth and redirect to `/login`.
- **403** → toast "You do not have permission for this action."
- **429** → toast "Too many requests. Please wait a moment."
- **5xx** → generic toast; log the request id.

The mock returns shapes the UI already branches on — `{reentry: true, alert}`,
`{dispute: true, alert}`, `{ok: false, reason}`. **Preserve those shapes.** They are
successful responses in the mock and must stay successful responses (200) from the
API where the UI treats them as such — specifically `distributorReceive` returning
`{dispute: true}` and `uploadCertificate` returning `{ok: false, reason}`. Only
genuinely refused operations (forwarding a disputed return, registering a destroyed
batch) return 409.

### Per-service migration checklist

Run this for each service file as its phase lands:

- [ ] Every exported function keeps its exact name and argument order
- [ ] Return shape matches the mock's, field for field (`camelCase` on the wire)
- [ ] `async` preserved; the artificial `delay()` removed
- [ ] Internal helpers that mutate state (`appendEvent`, `pushAlert`, `notify`) deleted, not ported
- [ ] Auth header attached — **except** in `verifyService.js`
- [ ] Errors surface as `ApiError`, not swallowed
- [ ] Every page that imports the service still renders — click through each route
- [ ] Loading and empty states still trigger correctly with real latency
- [ ] The relevant demo-path step still passes
- [ ] Mock path deleted only after the real path is verified — never both live at once

---

## Seed data spec

The backend seed must mirror `frontend/src/services/seed.js` exactly. The demo
depends on specific IDs, and the frontend's `KNOWN` map in `pages/pharmacy.jsx`
hardcodes three batch codes.

**Time base:** all dates derived from `DEMO_NOW = 2026-09-15T09:30:00+05:30`,
matching the frontend constant.

| Entity | Count | Notes |
| --- | --- | --- |
| Pharmacies | 10 | `ph_1`–`ph_10`, real Tamil Nadu names and coordinates, licenses `TN-RTL-20250`+ |
| Distributors | 3 | `dist_1`–`dist_3`; `dist_1` = "Sunrise Pharma Distributors" (demo path depends on it) |
| Agents | 7 | `agent_1`–`agent_7`; `agent_1` = "Ravi Kumar", belongs to `dist_1` |
| Vehicles | 5 | `veh_1`–`veh_5`, registrations `TN 11 AB 1000` style |
| Manufacturers | 4 | `mfr_1`–`mfr_4`; `mfr_1` = "Cipla Ltd." |
| Facilities | 3 | `fac_1`–`fac_3`, licenses `BMW-900`+ |
| Regulator | 1 | `reg_1` = "CDSCO — Tamil Nadu", officer R. Menon, `CDSCO-TN-4471` |
| Drugs | 9 | `DOX, CIS, CEF, MER, ATO, AML, PAR, MET, OME` with categories and prices |
| Batches | ~44 | 14 `ACTIVE`, 8 `EXPIRING_SOON`, 5 `EXPIRED`, 6 `IN_RETURN`, 9 `DESTROYED`, plus the two hero batches |
| Events | 10–20 per batch | Fully chained and signed at seed time |
| Returns | 6 | Spread across `REQUESTED`, `SCHEDULED`, `PICKED_UP`, `CONFIRMED`, `DISPUTED` |
| Routes | 2 | `route_1` (dist_1, 7 stops, active), `route_2` (dist_2, 3 stops, active) |
| Alerts | 5 | 3 `REENTRY`, 1 `QUANTITY_MISMATCH`, 1 `CERT_MISMATCH`; one `INVESTIGATING` |
| Notifications | ~7 | Seeded per role |
| Reports | 2 | CDSCO monthly, oncology quarterly |
| Users | 5 | The demo accounts, `is_demo = true`, real Argon2 hashes |

**The two hero batches are non-negotiable:**

- `BATCH-DOX-2026-A17` — Doxorubicin 50mg, Cipla, pharmacy `ph_1`, distributor
  `dist_1`, 50 units of 50, `EXPIRING_SOON`, expiring in 22 days.
- `BATCH-DOX-2026-B04` — Doxorubicin 50mg, Cipla, pharmacy `ph_3`, 40 units,
  `DESTROYED` 40 days ago, `certId = CERT-DOX-2026-B04-2026`, with a complete
  destruction chain.

`BATCH-FAKE-9999-Z01` must **not** exist — its absence is what produces the
`NOT_FOUND` verdict.

**Determinism:** seeding twice must produce identical rows apart from generated ids
and signatures. Use a fixed PRNG seed. `POST /api/demo/reset` re-runs this exactly,
and a demo that resets differently is a demo that fails on stage.

---

## Cut list

If time runs short, cut from the bottom up.

**Never cut — these are the product:**

1. The return flow (create → route → pickup → confirm → forward)
2. The dispute gate
3. Re-entry detection
4. Patient Shield (`/verify`)
5. Certificate binding

**Cut in this order:**

| # | Cut | Impact | Fallback |
| --- | --- | --- | --- |
| 1 | Docker, CI, monitoring (Phase 9) | None on the demo | Run locally |
| 2 | Real PDF generation | Reports list without downloadable files | Metadata only, as the mock does |
| 3 | Real photo upload | No stored images | Deterministic `photoHash` from batch + type + timestamp, as the mock does |
| 4 | Analytics long-horizon charts | Some charts show synthetic data | Deterministic generator, clearly marked `synthetic: true` |
| 5 | Entity compliance scoring | Regulator entities page thins out | Compute on the fly, no caching |
| 6 | Nightly quantity-cap sweep | Cap breaches only detected at registration | Registration-time check only — still catches the demo case |
| 7 | Notification persistence | Bell shows only what arrived this session | WebSocket push without a history table |
| 8 | Route auto-optimisation | Distributor orders stops manually | `manualOrder` path only |
| 9 | Refresh-token rotation | Slightly weaker session security | Long-lived access tokens, demo only |
| 10 | WebSocket real-time (Phase 7) | **Step 8 loses its ~2s timing** | 3-second polling on the regulator dashboard. Ugly, visibly slower, but the demo path still completes. Cut this only if the alternative is not finishing. |

Quantity-cap detection sits below the never-cut line as a *rule*, but its **nightly
sweep** is cuttable — registration-time checking is what the demo exercises.

---

## Open questions

Decisions I could not make from the code alone. Items marked **decided** have a
recommendation already written into `ARCHITECTURE.md` — override them there if you
disagree. Items marked **needs your call** are genuinely blocked on you.

### 1. Agent count vs distributor received quantity — **needs your call**

The agent records `pickedQuantity` (45). The distributor separately types
`quantityReceived`. Today the distributor's field starts empty and does not
pre-fill from the agent's count.

**Recommendation:** keep them independent. Do not pre-fill.

**Tradeoff:** pre-filling would fire the dispute automatically at pickup, which is
faster and needs one less human action. But two independent attestations are the
stronger fraud signal — if the distributor's number is seeded from the agent's, you
lose the ability to detect loss *between* the agent's van and the warehouse, which is
exactly the leg where units disappear. The demo path also reads as though the
distributor commits the number themselves at step 6. Independence is both better
evidence and truer to the script.

### 2. Certificate PDF — **needs your call**

The mock stores `{certId, fileName}` and no file.

**Recommendation:** metadata-only for the demo; real upload in Phase 9.

**Tradeoff:** a real PDF makes the certificate binding demo tangible and is
defensible to judges as a compliance artifact. But it needs object storage, upload
limits, virus scanning if it ever goes near production, and a viewer in the UI —
about a day of work for a step that currently takes one click. If you want the
tangibility, the cheap middle ground is: accept the upload, store the file's SHA-256
in the event, and discard the bytes. The hash is what proves binding anyway.

### 3. Analytics — real or synthetic? — **decided** (`ARCHITECTURE.md` §8.10)

**Decision:** hybrid. Compute everything the database can honestly answer; keep a
deterministic generator for long-horizon series, marked `synthetic: true`.

**Tradeoff:** fully computed analytics would be more honest, but a freshly seeded
database cannot produce a 24-month destruction trend without fabricating 24 months of
history — which is the same fabrication, just hidden in the seed instead of labelled
in the response. Marking it is the honest version.

### 4. Notification scoping — **decided** (`ARCHITECTURE.md` §4.8)

**Decision:** keep `getNotifications(role)` as the signature; scope server-side to
the authenticated user plus role-wide broadcasts.

**Tradeoff:** the frontend keeps its contract and no screen changes, at the cost of a
slightly misleading function name — it takes a role but returns a user-scoped list.
Renaming it would be cleaner and would violate rule 3.

### 5. Regulator entity — **decided** (`ARCHITECTURE.md` §4.2)

**Decision:** add a `regulators` table so `reg_1` resolves, and move the hardcoded
officer details out of `regulator.jsx` Profile into seeded data.

**Tradeoff:** one more table for a single row today. The alternative — regulators as
users with no entity — leaves `entityId: "reg_1"` in the auth store pointing at
nothing, which will confuse whoever touches this next. Worth the table.

### 6. `DEMO_NOW` — **decided** (`ARCHITECTURE.md` §4.10)

**Decision:** pin the backend to `2026-09-15T09:30+05:30`, matching the frontend
constant.

**Tradeoff:** the demo is frozen in a fixed present, and the gap between it and real
wall-clock time grows. Seeding relative to real `now` would be more natural, but the
frontend does all its day-math against `DEMO_NOW`, so "22 days to expiry" would
render wrong on the hero batch — and fixing that means editing frontend files, which
rule 3 forbids. Revisit if the demo is still running months from now.

### 7. Database — **decided** (`ARCHITECTURE.md` §1.2)

**Decision:** PostgreSQL. Full comparison against MongoDB is in §1.2.

**Tradeoff:** Mongo would let us store `batch.events[]` as an embedded array matching
the frontend shape exactly, and would start faster with no migrations. Postgres costs
us Alembic setup but buys database-level enforcement of the hash chain's uniqueness
constraints — which is the difference between "the code is careful" and "the storage
layer refuses". For a system whose pitch is tamper-evidence, that is the right trade.
**Confirm this before Phase 1 — it is expensive to reverse after Phase 4.**

### 8. Signing keys — **decided** (`ARCHITECTURE.md` §7.5)

**Decision:** per-entity Ed25519 keypairs generated at seed time, private keys
encrypted at rest, server signs on the actor's behalf.

**Tradeoff:** this proves *the server recorded this actor's action in this order* —
not that the actor personally signed it. True client-held keys would be a stronger
claim, but require key distribution to pharmacies and agents on mobile, and key
recovery when a phone is lost. That is a real product, not a hackathon phase. The
tamper-evidence property holds either way, and §7.5 states the limitation honestly
rather than overclaiming.

### 9. Public endpoint abuse — **decided** (`ARCHITECTURE.md` §6.6)

**Decision:** rate limit by IP (30/min verify, 5/min report), hash and store the IP
on patient reports for pattern analysis. No captcha.

**Tradeoff:** a determined actor could still flood the regulator's alert feed with
fake patient reports from rotating IPs. A captcha would stop that and would also stop
a frightened patient with a suspicious pill bottle, which defeats the point of the
feature. If flooding becomes real, the answer is server-side clustering of reports
into a single alert — not friction at the front door.

### 10. `listBatches` returning everything — **needs your call**

The mock returns every batch to every caller and filters client-side. `ARCHITECTURE.md`
§8.2 specifies role scoping plus pagination.

**Recommendation:** scope and paginate from Phase 2.

**Tradeoff:** with ~44 seeded batches, scoping changes nothing visible and paginating
changes nothing visible — so this is free now and expensive later. The risk is that a
page silently filters on a field the server has already removed from its scope,
producing an empty table. Worth one careful pass through the three consuming pages
(pharmacy Inventory, manufacturer Batches, regulator Batches) when it lands.

### 11. Return status enum — **decided** (`ARCHITECTURE.md` §5.2)

**Decision:** seven canonical statuses. Accept `ASSIGNED` and `EN_ROUTE` on input as
aliases of `SCHEDULED`; never emit them.

**Tradeoff:** the pharmacy tracking stepper maps nine statuses, and two of them will
now never arrive. That is harmless — the stepper maps them to the same index as
`SCHEDULED`. The alternative, keeping nine states, means two states with no
transitions into them and no meaning distinct from `SCHEDULED`.
