# CONTEXT — What DOT is

Orientation for anyone new to this repo. For rules, see `CLAUDE.md`. For the
system design, see `ARCHITECTURE.md`. For the build order, see `BUILDPHASES.md`.

---

## The problem

When medicine expires on a pharmacy shelf in India, there is no enforced path for
what happens next. The pharmacy is supposed to send it back up the supply chain —
to the distributor, then the manufacturer, then a licensed destruction facility —
but nothing tracks whether that actually happened.

That gap is where the fraud lives. Expired stock gets bought cheaply, relabelled
with a fresh printed batch number, and resold. This is not hypothetical and it is
not limited to cheap drugs: oncology drugs and injectable antibiotics are among
the products that reappear. A patient receiving relabelled expired Doxorubicin has
no way to know.

In May 2025, India's CDSCO issued a mandate requiring a formal reverse-logistics
pathway for expired drugs. The mandate exists. The software to operationalise it
does not. DOT is that software.

## What DOT is

A closed-loop trust registry for the pharmaceutical reverse supply chain. Every
expired batch is tracked from the pharmacy shelf, through the distributor, to the
manufacturer, to certified destruction — and every step is recorded in a
tamper-evident event log that a regulator can audit and a patient can query.

The loop is *closed* in a specific sense: a batch cannot quietly leave the system.
Once it enters the return flow, the only exit is a destruction certificate bound
to a confirmed chain of custody. If a batch that reached that exit ever reappears
in circulation, the system knows immediately.

## The six users

| Interface       | Role           | What they do                                                  |
| --------------- | -------------- | ------------------------------------------------------------- |
| `/pharmacy`     | RETAILER       | Registers stock, records sales, initiates returns on expiring batches |
| `/distributor`  | DISTRIBUTOR    | Receives return requests, plans pickup routes, verifies received quantities, forwards to manufacturer |
| `/agent`        | PICKUP_AGENT   | Mobile-first. Drives the route, marks arrival, counts and collects at each stop |
| `/manufacturer` | MANUFACTURER   | Schedules licensed destruction facilities, uploads destruction certificates |
| `/regulator`    | REGULATOR      | CDSCO officer. Monitors alerts, audits any batch's full history, scores entity compliance, exports reports |
| `/verify`       | *public patient* | Scans a medicine's QR code and gets a plain-language verdict. **No login.** |

## How the flow works, end to end

1. A pharmacy registers a batch into inventory (scan or manual entry).
2. As expiry approaches, the batch is flagged `EXPIRING_SOON`. The pharmacy
   photographs the strip, confirms the remaining quantity, picks a distributor,
   and starts a return.
3. The distributor sees the request, groups it with nearby returns into a pickup
   route, assigns an agent and a vehicle, and dispatches. The vehicle is now
   visible, live, on every stakeholder's map.
4. The agent arrives at the pharmacy, counts the physical units, and completes the
   pickup. That count is an independent attestation — it is not assumed to match
   what the pharmacy claimed.
5. The distributor verifies what actually arrived at the warehouse. If the count
   matches the pharmacy's claim, the return is confirmed. If it does not, the
   chain halts.
6. Once confirmed, the distributor forwards the batch to the manufacturer.
7. The manufacturer schedules a licensed destruction facility and uploads the
   destruction certificate. The batch flips to `DESTROYED`.
8. If that destroyed batch is ever scanned again — at any pharmacy, or by any
   member of the public — an alert fires immediately.

## What makes it more than CRUD

Five mechanisms carry the actual product value. Everything else in the system
exists to make these possible.

**Re-entry detection.** A batch marked `DESTROYED` that gets scanned again anywhere
fires a critical alert to the regulator and the manufacturer within seconds. The
registration is refused. This is the direct counter to relabel-and-resell fraud
where the original batch number is reused.

**Quantity-cap check.** Sophisticated fraudsters do not reuse destroyed batch
numbers — they print *new* ones. Destroyed-batch matching alone cannot catch that.
So DOT also tracks how many units of a batch were ever manufactured, and flags
when more units than that appear in circulation. Counterfeit stock has to exist
*somewhere* in the count, and the count is the thing that cannot be forged.

**The dispute gate.** When the distributor's received count does not match the
pharmacy's claimed count, the chain stops. Nothing advances — no forwarding, no
scheduling, no certificate — until a human files resolution notes. Missing units
between shelf and warehouse are exactly the units that end up back on the market,
so a quantity mismatch is treated as a fraud signal, not a rounding error.

**Certificate binding.** A destruction certificate cannot be created for a batch
that has not cleared distributor confirmation. This prevents the laundering move
of certifying the destruction of goods that were never actually collected —
paperwork claiming a batch died while the batch is still in circulation.

**The tamper-evident event log.** Every event on a batch — registration, sale,
return, pickup, confirmation, forwarding, destruction — is hash-chained to the
event before it and signed by the actor who performed it. Rewriting history
requires reforging every subsequent link, and the forger still cannot produce the
other actors' signatures. This gives a regulator a court-usable audit trail.
There is no blockchain involved and none is needed.

**Patient Shield** (`/verify`) is the public face of all of it. Anyone can scan a
box and get one of three answers: genuine, not found, or a red
**DO NOT USE THIS MEDICINE**. No account, no app install, no data collection. It
is the part of the system a patient actually touches, and it is the reason the
rest of the system has to be trustworthy.

## Current state of the repo

The frontend is complete and working. It runs entirely on mocked data held in an
in-memory store persisted to `localStorage`, seeded with ~44 batches, 10
pharmacies, 3 distributors, 4 manufacturers and 3 destruction facilities across
Tamil Nadu.

Every read and write in the frontend already goes through a typed service layer in
`frontend/src/services/`. Those function signatures are the backend contract — see
`ARCHITECTURE.md`.

The backend is real as far as Phase 2 goes. `backend/` is a full FastAPI +
async SQLAlchemy + Alembic app (Phase 0), with real Argon2/JWT auth, the
role → permission matrix, and Postgres-backed reference data for pharmacies,
distributors, manufacturers, facilities, regulators, agents, vehicles and
drugs (Phase 1). The five demo accounts are real seeded database users
authenticating through the real login code path.

Phase 2 adds the real batch ledger and the append-only, hash-chained event
log: `POST /api/batches` registers a batch and appends a real, Ed25519-
signed `REGISTERED` event in the same transaction; `POST
/api/batches/{id}/sale` decrements quantity and appends a `SALE` event the
same way; `GET /api/batches/{id}/verify-chain` walks a batch's full event
history and genuinely detects tampering (a modified hash, `meta`,
`prev_hash`, or signature; a removed event) and chain forks (the database's
own `UNIQUE` constraints refuse those outright). The seed now includes ~44
batches with complete, independently-verifiable event histories, including
both hero batches (`BATCH-DOX-2026-A17` expiring-soon, `BATCH-DOX-2026-B04`
already destroyed with a complete 8-event chain) — see `BUILDPHASES.md`.

Phase 3 adds the fraud engine and Patient Shield — the first two of the
five never-cut capabilities to go live. `fraud_service.py` implements
re-entry detection (wired into `POST /api/batches` and `POST
/api/batches/{id}/sale`: registering or selling against a batch already
marked `DESTROYED` is refused with `409 BATCH_DESTROYED_REENTRY`, a
critical alert, and a `REENTRY_BLOCKED` event) and the quantity-cap check
(implemented and independently tested, though it has no live trigger
through the API yet — see BUILDPHASES.md's Phase 3 notes for why).
`alert_service.py` and the `alerts` table back `GET /api/alerts`, `GET
/api/alerts/{id}`, and regulator-only `PATCH /api/alerts/{id}/status`,
with the category → severity → recency priority ordering applied
server-side. The public router (`/api/public/verify/{batchId}`, `/api/public/report`)
carries no auth dependency anywhere — enforced by a test that scans the
live route table — and is rate-limited. Demo steps 8 and 9 both work
end to end: scanning the pre-destroyed `BATCH-DOX-2026-B04` fires a
real re-entry alert, and `/verify` returns the correct verdict for all
three demo codes with zero credentials.

Phase 4 adds the return flow and its dispute gate — the third of the five
never-cut capabilities. `return_service.py` implements the full lifecycle:
`POST /api/returns` (create, RETAILER-only, with ownership/state/quantity
checks and re-entry reuse for a destroyed batch), `PATCH
/api/returns/{id}/receive` (the distributor's independent quantity
attestation — a match confirms and appends `DISTRIBUTOR_CONFIRMED`; a
mismatch fires `DISPUTED` plus a real `QUANTITY_MISMATCH` alert, with no
batch event and no holder change until it clears), `PATCH
/api/returns/{id}/resolve` (requires non-blank resolution notes, appends
`DISPUTE_RESOLVED`, closes the alert), `POST /api/returns/forward` (blocked
by the shared `assert_not_disputed` guard — calling it directly on a
disputed return, no UI involved, is a real `409 CHAIN_HALTED_DISPUTE`), and
`PATCH /api/returns/{id}/status` (the Kanban drag endpoint, now with real
forward-only transition validation the mock never had). The three quantity
attestations — `quantityClaimed`, `pickedQuantity`, `quantityReceived` —
stay genuinely independent everywhere; nothing auto-copies one into
another. `notification_service.py` and the new `notifications` table give
Phase 4 write-only notification persistence (read endpoints are Phase 8's
job). Two concurrent `receive` calls on the same return resolve to exactly
one outcome via real PostgreSQL row locking. Demo steps 1, 2, 3, and 6 all
work end to end on a real backend, verified against a live server, not
only pytest.

Pickups, certificates, analytics, and WebSockets do not exist yet — that
starts at Phase 5. Alerts and notifications are not seeded on reset (the
alert types and lifecycle notifications that depend on returns/pickups/
certificates can't be seeded honestly until each phase exists); a demo
session gets its first alert and notification live, from an actual
action — re-entry attempt, patient report, or return-flow state change.

The frontend swap is done. Every function in `frontend/src/services/*.js`
now calls the real backend — no mock, no `localStorage` fake store,
`src/services/seed.js` deleted. `src/store/authStore.js` calls the real
`/api/auth/login` and `/api/auth/demo-login`; `Login.jsx`'s email/password
fields (previously present but inert) actually authenticate now.
`src/services/db.js` is a client-side cache bootstrapped by REST on login,
kept current by a targeted re-fetch after every mutating call, and patched
live by a real WebSocket connection to `/api/ws` when a message arrives —
`hooks/useDb.js`'s `useLive` seam needed zero changes, which is exactly
what it was built for. See `BUILDPHASES.md`'s "Frontend swap plan —
EXECUTED" for the full file list, the handful of real contract mismatches
that turned up (and how each was resolved without touching a `pages/*.jsx`
file), and a backend bug this work found and fixed
(`batch_status.derive_status` crashed on any real client-supplied
date-only expiry — seeded data never exercised it).

All nine demo-path steps were walked in a real browser (headless Chromium
via Playwright, driving a real `npm start` dev server against a real
`uvicorn` server) end to end, through real login/demo-login — not curl,
not the mock. Confirmed live in-browser: single-batch registration, the
return flow, the dispute gate firing on a genuine quantity mismatch and
blocking `forward` until resolved, certificate upload flipping a batch to
`DESTROYED`, re-entry detection firing a real alert the regulator dashboard
picks up, and the public `/verify` route (logged out, no account)
correctly rendering the red "DO NOT USE" verdict for a destroyed batch.
Also confirmed live: a single-flight silent token refresh recovers a
corrupted/expired access token without dropping the user's session; a
logged-out refresh token genuinely fails on reuse; a wrong-role token gets
a real 403; and all six routes (`/pharmacy`, `/distributor`, `/agent`,
`/manufacturer`, `/regulator`, `/verify`) load with zero real console
errors.

**Update — live WebSocket push is now real and verified, not just
degraded-gracefully.** A real Redis is running locally (`backend/.env`'s
`REDIS_URL` points at it) and a genuine, serious bug in
`core/realtime.py` — the pub/sub fan-out silently dropped every message
even with Redis fully working, a `redis.asyncio` PubSub single-task-owner
violation — was found and fixed. Vehicle GPS positions now tick live over
the WebSocket (confirmed: a dispatched route's position frames arriving
in real time, genuinely moving), and a 50-connection load test against a
real re-entry-triggered alert delivered to all 50 clients in under 0.7s.
Full account in `BUILDPHASES.md`'s "Round 2" section and
`ARCHITECTURE.md` §11. The app still degrades cleanly to
REST-refresh-after-mutation if Redis isn't reachable (unchanged, still
correct) — that path is just no longer the only one that's been proven to
work.

Also wired in this round: real photo capture (`POST /api/uploads/photo`)
in both return-flow photo steps — the pharmacy's strip photo and the
distributor's received-goods photo are real uploaded images with a real
server-computed hash now, not placeholder strings, and both flows require
one before submitting. The `addBatch`/`uploadCertificate` response-shape
mismatches from the first pass are resolved by correcting the two stale
table entries in `ARCHITECTURE.md` (the backend's real 409s were already
right) rather than carrying a frontend shim; `InventoryAdd`'s missing
`unitPrice`/`manufacturerId` fields are resolved by the form actually
collecting them (real drug/manufacturer pickers) instead of a
service-layer guess.

## Demo batch codes

| Code                  | Meaning                                                   |
| --------------------- | --------------------------------------------------------- |
| `BATCH-DOX-2026-A17`  | Doxorubicin 50mg, genuine, expiring soon — the hero batch |
| `BATCH-DOX-2026-B04`  | Already destroyed — triggers re-entry alert and the red Patient Shield verdict |
| `BATCH-FAKE-9999-Z01` | Not in the registry — counterfeit / unverifiable          |
