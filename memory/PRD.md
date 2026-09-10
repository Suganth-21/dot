# DOT — Product Requirements & Build Log

## Problem statement (original)
Closed-loop compliance & fraud-detection platform for India's pharmaceutical reverse supply chain.
Tracks expired medicines from pharmacy shelf → distributor → manufacturer → licensed destruction,
with a public patient-facing verification page. CDSCO-aligned reverse logistics. Frontend-only build
with realistic mock data behind a swappable service layer.

## Architecture
- React 18 (CRA) + React Router 6, Tailwind (custom claymorphic pastel bento design system).
- State: Zustand (auth, persisted), in-memory reactive store `services/db.js` (localStorage-persisted,
  cross-tab storage sync, setInterval simulation for live vehicle markers + notifications).
- Data fetching: TanStack Query over a service layer (`services/*.js`) — trivial backend swap.
- Charts: recharts. Maps: react-leaflet + OSM. QR: html5-qrcode (with demo-scan fallback). Motion: Framer Motion. Toasts: sonner.
- Minimal FastAPI stub at /app/backend only so supervisor stays green (unused by the app).

## User personas / roles
RETAILER (Pharmacy), DISTRIBUTOR, PICKUP_AGENT (mobile), MANUFACTURER, REGULATOR (CDSCO), + public patient.

## Core requirements (static)
6 interfaces (5 role-gated + public Patient Shield), shared batch ledger, hash-chained event log,
re-entry fraud detection, distributor dispute gate, manufacturer certificate-binding enforcement,
live maps, notifications, ⌘K search, all empty/loading/error states designed.

## Implemented (2026-06)
- All 6 interfaces, every route/page in the spec, all charts + maps + QR + hash-chain timeline.
- Full demo path working end-to-end via mocks (add → return → route → pickup → dispute → forward →
  schedule → certificate → DESTROYED → re-entry alert → Patient Shield red).
- Seed: 10 pharmacies, 3 distributors (agents+vehicles), 4 manufacturers, 3 facilities, ~45 batches
  across all statuses, 15+ events/batch, pre-fired re-entry alerts, 2 active animated routes.
- Reset Demo button, README with demo script, test_credentials.md.
- Verified by testing agent: all 5 never-cut flows PASS, ~97% frontend success. Fixed QrScanner
  unmount runtime errors post-test.

## Backlog / next (P1/P2)
- DONE (2026-06): Kanban drag-and-drop in distributor Inbox — cards drag between
  NEW/SCHEDULED/PICKED_UP/CONFIRMED via native HTML5 DnD (`returnService.setReturnStatus`),
  with column drop-highlight and status side-effects (events/holder updates); disputed returns are blocked from dragging.
- DONE (2026-06): Route reorder drag on the route builder (`PickupNew`) — draggable ordered
  stop list, live path-polyline preview reflecting order, "Auto-optimise" (nearest-neighbour) button,
  builder pre-populates from Inbox selection; `createRoute({manualOrder})` respects the arranged order.
- P1: Invoice OCR (currently placeholder), real Sankey (recharts Sankey) for manufacturer flow.
- P2: choropleth GeoJSON of India (currently district cards + bubble maps), PDF export polish,
  silence recharts defaultProps React-18 warning.
- Backend swap: replace service-fn bodies with fetch calls.
