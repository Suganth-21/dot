# CLAUDE.md — Project rules

Permanent rules for this repository. These do not expire and are not overridden by
convenience, deadline pressure, or a passing instruction in a single prompt.

Build steps, phase ordering, and anything temporary belongs in `BUILDPHASES.md`,
not here. System design belongs in `ARCHITECTURE.md`. Orientation is in
`CONTEXT.md`.

---

## 1. Never run git commands

Never run `git add`, `git commit`, `git push`, `git reset`, `git checkout`,
`git rebase`, `git stash`, or any other command that mutates git state. Never
create branches, tags, or PRs.

The human on this project handles all staging and committing themselves. Read-only
inspection (`git status`, `git log`, `git diff`) is acceptable when explicitly
asked for and nothing else. If work seems ready to commit, say so and stop.

## 2. Never bypass a domain rule in the API layer

Assume every request is hostile and hand-crafted. Assume the UI is not involved.

Every domain rule below is enforced **server-side, in the service layer, inside the
transaction that performs the write**. Not in the frontend. Not in a React
component. Not in a validator that a different endpoint can skip. Not in
middleware that a new route forgets to register.

The non-negotiable rules:

- **Dispute gate** — a return whose distributor-confirmed quantity differs from the
  retailer-claimed quantity is `DISPUTED`, and a `DISPUTED` return cannot be
  forwarded, scheduled, or certified until resolution notes are recorded. There is
  no flag, query parameter, or admin role that skips this.
- **Certificate binding** — a destruction certificate cannot be created for a batch
  that has not cleared distributor confirmation and been forwarded. No orphan
  certificates. No certificate for a batch already `DESTROYED`.
- **Re-entry detection** — registering, scanning, or transacting a `DESTROYED`
  batch fires a critical alert to the regulator and the manufacturer and refuses
  the registration. It is never silently allowed.
- **Quantity-cap check** — units of a batch in circulation may never exceed the
  units ever manufactured for that batch. Exceeding it raises an alert.
- **Append-only event log** — events are inserted, never updated and never deleted.
  There is no `UPDATE` and no `DELETE` on the events table, in any code path, ever.
- **Hash chain integrity** — every event links to the hash of the previous event on
  that batch, and carries its actor's signature. Never write an event without
  computing the chain link. Never recompute or rewrite an existing event's hash.

If a rule makes a feature awkward, the feature changes. The rule does not.

A test that asserts a rule cannot be bypassed is worth more than a test that
asserts the happy path works. Write both; never ship only the second.

## 3. The frontend service layer is the contract

`frontend/src/services/*.js` defines the shape of this system. The backend conforms
to the frontend, not the other way round.

- Function names, argument shapes, and return shapes in the service layer are the
  API contract. Preserve them.
- **No frontend screen may be redesigned to suit the backend.** If an endpoint is
  awkward to implement, fix the endpoint's implementation — not the screen that
  consumes it.
- Backend swap means replacing the *body* of a service function with a `fetch`
  call. The exported signature stays identical. Anything else is a contract break.
- If a response genuinely cannot match the existing shape, raise it as an explicit
  decision to a human before changing either side. Do not silently reshape.
- Field names cross the wire exactly as the frontend already reads them:
  `quantityClaimed`, `quantityReceived`, `drugName`, `batchId`, `prevHash`,
  `photoHash`, `entityId`, `distributorId`, `manufacturerId`, `certId`,
  `scheduledFacility`, `holder`. Do not rename to a "cleaner" convention.

## 4. `/verify` is public, permanently

The Patient Shield route and every endpoint it calls are open to unauthenticated
requests. Forever.

- No auth wall, no login prompt, no redirect to `/login`, no "sign in to see full
  details", no soft gate, no cookie requirement.
- Never add an auth dependency to a `/api/public/*` route. Never let a global auth
  middleware cover that prefix.
- A patient holding a suspicious medicine box must get an answer in one scan with
  zero friction. That is the product.
- Public endpoints are rate-limited and return deliberately minimal data. They are
  never protected by making them harder to reach.

## 5. No blockchain

Integrity comes from a signed hash chain in a normal database. That is a deliberate
architectural decision, not a placeholder.

Do not introduce a blockchain, a distributed ledger, a smart contract, a token, or
an external anchoring service. Do not suggest one. If someone asks how the system
achieves tamper-evidence without a blockchain, the answer is in `ARCHITECTURE.md`,
and it is a better answer for this problem.

## 6. Stack

Fixed decisions. Do not swap these without an explicit human decision.

- **Backend:** Python 3.11+, FastAPI, uvicorn. All routes under the `/api` prefix.
- **Database:** PostgreSQL. SQLAlchemy 2.0 (async) + Alembic for migrations.
- **Auth:** JWT access + refresh tokens. Argon2 password hashing. Never store or
  log a plaintext password.
- **Real-time:** WebSockets served by FastAPI, fanned out via Redis pub/sub.
- **Hashing:** SHA-256 over canonical JSON. Ed25519 for actor signatures.
- **Frontend:** React 18 (CRA), React Router 6, TanStack Query, Zustand, Tailwind.
  Already built — do not upgrade, migrate, or re-bundle it as a side quest.

## 7. Code standards

- **Clean architecture.** Routers handle HTTP. Services hold domain logic.
  Repositories touch the database. Domain rules live in services, never in routers
  and never in models. A router that contains an `if` about business meaning is a
  bug.
- **Modular and reusable.** Shared logic gets extracted. No copy-pasted rule
  checks — a rule is implemented once and called from everywhere it applies.
- **Real error handling.** No bare `except:`. No swallowed exceptions. No `pass` in
  an error path. Every failure returns a structured error with a machine-readable
  code and a human-readable message. A caller must be able to tell *why* something
  failed, not just that it did.
- **Typed.** Pydantic models for every request and response. No bare `dict`
  crossing a service boundary.
- **Transactions.** Any operation that writes more than one row — and every
  operation that appends an event — runs in a single transaction. Partial writes to
  an append-only log are not recoverable.
- **No secrets in code.** Configuration comes from environment variables. Never
  commit a real credential, key, or token.
- **No placeholder implementations.** Do not write `# TODO: implement`, do not
  return hardcoded success, and do not stub a domain rule "for now". If something
  cannot be finished, say so explicitly rather than leaving a function that lies
  about working.
- **Comments explain why, not what.** Match the surrounding style.

## 8. Demo integrity

The end-to-end demo path in `BUILDPHASES.md` must keep working after every change.
It is the acceptance test for the whole system.

The five never-cut capabilities are the return flow, the dispute gate, re-entry
detection, Patient Shield, and certificate binding. Nothing gets cut, stubbed, or
feature-flagged out of those five.

The five one-click demo logins must keep working, and they must work *through real
auth* — real users, real password hashes, real tokens. They are a seeded
convenience, never a bypass of the auth system.
