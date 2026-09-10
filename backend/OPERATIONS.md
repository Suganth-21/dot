# OPERATIONS — backups, key rotation, and other Phase 9 runbook items

Not part of the demo (BUILDPHASES.md Phase 9 is explicitly cuttable and
not required for it). Written so a real deployment has a starting point,
not left as a silent gap.

---

## Database backups

`DATABASE_URL` points at a normal PostgreSQL database — back it up the
normal way. No DOT-specific logic is required; the append-only event
chain doesn't change how backup/restore works.

**Daily logical backup (cron / scheduled task):**

```bash
pg_dump --format=custom --file="dot-$(date +%F).dump" "$DATABASE_URL"
```

Keep at minimum 7 daily + 4 weekly backups off the database host itself
(a second disk, object storage, whatever the deployment target offers).

**Restore:**

```bash
pg_restore --clean --if-exists --dbname="$DATABASE_URL" dot-2026-09-19.dump
```

**Before restoring into a database anyone might currently be reading
from:** stop the API process first. `pg_restore --clean` drops and
recreates objects; a live connection mid-restore sees a broken schema.

**What backup does *not* need to account for:** the hash chain's integrity
doesn't depend on backup timing — `verify-chain` re-derives everything
from stored fields on read, so a restored database is exactly as valid as
the moment it was dumped, no chain re-signing or replay needed.

---

## Key rotation

Two secrets need real rotation procedures: `JWT_SECRET` and
`SIGNING_MASTER_KEY`. Never rotate either by editing `.env` and restarting
mid-day without reading the consequence below — both invalidate things.

### `JWT_SECRET`

Rotating it invalidates **every currently-issued access and refresh
token** — every logged-in user is signed out immediately. Acceptable for a
scheduled maintenance window; never do it silently during active traffic
without warning users.

1. Generate a new secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Set it as `JWT_SECRET` in the environment for all API processes.
3. Restart every API process (they all need the same secret; a rolling
   restart with mismatched secrets across instances will intermittently
   401 requests routed to the not-yet-restarted ones).
4. Communicate the forced logout to users ahead of time if possible.

### `SIGNING_MASTER_KEY`

This decrypts every entity's stored Ed25519 **private** key
(`app/core/crypto.py`). Rotating it without a migration step makes every
previously-encrypted private key unreadable — new events would fail to
sign, and old ones would still verify fine (signatures don't depend on the
key being decryptable *again*, only on having been valid when created).

**Correct rotation procedure — never just swap the value:**

1. Decrypt every entity's `signing_private_key` under the **old**
   `SIGNING_MASTER_KEY`.
2. Re-encrypt each one under the **new** key.
3. Write all rows back in the same transaction (all-or-nothing — a partial
   rewrite leaves some entities unable to sign).
4. Only then update the deployed `SIGNING_MASTER_KEY` and restart.

There is no ready-made script for this in the repo yet — write one before
the first real rotation is needed; do not attempt it by hand against
production data. The `app/core/crypto.py` functions
(`decrypt_signing_private_key`, `generate_signing_keypair`'s encryption
half) are the primitives to build it from.

**Public keys never need rotation for confidentiality** — only if a
private key is suspected compromised, in which case that single entity
needs a fresh keypair (not a master-key rotation), and every event it
signed going forward uses the new key while old events keep verifying
under the old public key stored via `signer_key_id`.

---

## Monitoring / error tracking

Not wired up. A real deployment should add:

- An APM/error-tracking SDK (e.g. Sentry) initialized in `app/main.py`
  before route registration, gated on a `SENTRY_DSN` (or equivalent)
  environment variable so local/dev runs never require one.
- A `/metrics` endpoint (Prometheus-style) if the deployment target scrapes
  metrics — request counts and latencies are the minimum useful set; the
  existing `RequestIDMiddleware` (`app/core/middleware.py`) is the natural
  place to add counters, since every request already passes through it.

Both were left out of this pass because they need an operator-supplied
external account/DSN this environment doesn't have — implementing a fake
one would violate CLAUDE.md's "no placeholder implementations" rule more
than leaving the gap documented does.

---

## Load testing the WebSocket fan-out

`backend/scripts/ws_load_test.py` opens N concurrent WebSocket connections
against `/api/ws`, subscribes each to `alerts:regulator`, and measures how
long a published alert takes to reach every connected client — the
ARCHITECTURE.md §9's "alert arrives in under 2 seconds" requirement, under
load instead of the single-client case the test suite can exercise.

Not run as part of this delivery (real load tests hit a real running
server and are a deliberate, separate action, not something to fire during
an unattended build pass). Run it yourself:

```bash
python scripts/ws_load_test.py --url ws://localhost:8000/api/ws --connections 200
```
