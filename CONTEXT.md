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

Returns, pickups, the fraud engine (re-entry detection, quantity-cap),
certificates, Patient Shield, analytics, notifications, WebSockets, and
every other later-phase feature do not exist yet — that starts at Phase 3.
Batch registration currently rejects any duplicate id outright; it does not
yet distinguish "already exists" from "was destroyed and is reappearing"
(that distinction, and the alert it fires, is Phase 3's re-entry detection).

The frontend still runs entirely on its own mocked data — nothing in
`frontend/src/services/*.js` has been pointed at the backend yet. That swap
is deliberately staged phase by phase (see `BUILDPHASES.md`'s "Frontend
swap plan"); Phases 1 and 2 built the backend side of the contract without
editing any frontend file.

## Demo batch codes

| Code                  | Meaning                                                   |
| --------------------- | --------------------------------------------------------- |
| `BATCH-DOX-2026-A17`  | Doxorubicin 50mg, genuine, expiring soon — the hero batch |
| `BATCH-DOX-2026-B04`  | Already destroyed — triggers re-entry alert and the red Patient Shield verdict |
| `BATCH-FAKE-9999-Z01` | Not in the registry — counterfeit / unverifiable          |
