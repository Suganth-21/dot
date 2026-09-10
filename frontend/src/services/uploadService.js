import { apiUpload } from "../lib/api";

// Real photo capture -> POST /api/uploads/photo. Additive (BUILDPHASES.md
// Phase 9) — no existing service function's contract changes; this backs
// the photo-capture buttons in returnService's callers (pharmacy.jsx's
// ReturnNew, distributor.jsx's ReturnDetail) with a real server-computed
// SHA-256 hash and a real stored file instead of a client-side placeholder
// string.
export async function uploadPhoto(file) {
  return apiUpload("/uploads/photo", file);
}
