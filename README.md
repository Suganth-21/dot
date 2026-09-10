# DOT — Pharmaceutical Trust Registry (Frontend)

A closed-loop compliance & fraud-detection platform for India's pharmaceutical reverse supply chain.
Tracks expired medicines from pharmacy shelf → distributor → manufacturer → licensed destruction,
with a public patient-facing verification page.

**This repo is frontend-only.** All data is mocked in an in-memory store (`/src/services/*`)
persisted to `localStorage`, so the backend swap is trivial — every read/write already goes
through a typed service layer.

## Tech stack
- React 18 + React Router 6 + Tailwind CSS (custom claymorphic bento design system)
- TanStack Query for data fetching (service layer adapters)
- Zustand for auth state
- Recharts for charts · react-leaflet + OpenStreetMap for maps · html5-qrcode for scanning
- Framer Motion for micro-interactions · Sonner for toasts

## Run
```bash
cd frontend
yarn install
yarn start        # http://localhost:3000
```

## Six interfaces
| Route root   | Role          | Login |
|--------------|---------------|-------|
| `/pharmacy`  | RETAILER      | yes   |
| `/distributor` | DISTRIBUTOR | yes   |
| `/agent`     | PICKUP_AGENT (mobile-first) | yes |
| `/manufacturer` | MANUFACTURER | yes |
| `/regulator` | REGULATOR     | yes   |
| `/verify`    | Patient Shield (public) | no |

Login at `/login` — use the 5 one-click demo accounts (no password needed).

## Cross-cutting
- Real-time notifications (bell), global ⌘/Ctrl-K batch search, toast on every state change
- Hash-chain event timeline on every batch detail (hover a "hash link" to see the hash)
- Live animated vehicle markers on all fleet/tracking maps
- Every event logged with timestamp + actor + GPS + photo hash (surfaced in the regulator audit trail)
- "Reset demo data" in the profile menu re-seeds everything

## The demo path (works end-to-end via mocks)
1. Log in as **Pharmacy Portal** → `Inventory → Add Stock` → scan **BATCH-DOX-2026-A17** (Doxorubicin) → register 50 units.
2. `BATCH-DOX-2026-A17` is pre-seeded as **EXPIRING_SOON**. Open it → **Start Return** → photograph → confirm 50 → select **Sunrise Pharma Distributors**.
3. Log in as **Distributor Portal** → the new return appears in **Inbox** (NEW).
4. Select it → **New route** → assign agent + vehicle → **Dispatch**. Vehicle starts moving on the map.
5. Log in as **Pickup Agent App** → **Start Route** → open the stop → **I have arrived** → enter **45** → **Pickup complete**.
6. Back in **Distributor** → open the return → **dispute gate** fires (amber, "Quantity Dispute — Chain Halted"). Fill resolution notes → **Forward to manufacturer**.
7. Log in as **Manufacturer Portal** → **Facilities → Schedule** → **Certificates → Upload** (blocked until distributor-confirmed) → submit → batch flips to **DESTROYED**.
8. Any pharmacy → `Add Stock` → scan **BATCH-DOX-2026-B04** (pre-destroyed) → **re-entry alert** fires on the **Regulator** dashboard within ~2s.
9. Open **`/verify`** (public) → scan **BATCH-DOX-2026-B04** → 🔴 **DO NOT USE THIS MEDICINE**.

### Handy demo batch codes
- `BATCH-DOX-2026-A17` — genuine / active
- `BATCH-DOX-2026-B04` — destroyed (re-entry + Patient Shield red)
- `BATCH-FAKE-9999-Z01` — not found / counterfeit

## Backend swap
Replace the bodies in `src/services/*.js` with real `fetch` calls. The interfaces are the contract.
