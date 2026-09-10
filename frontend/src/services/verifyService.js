import { publicGet, publicPost } from "../lib/api";

// Public Patient Shield verification — CLAUDE.md rule 4: no auth header,
// ever. publicGet/publicPost (src/lib/api.js) never attach Authorization.
export async function verifyBatch(batchId) {
  return publicGet(`/public/verify/${encodeURIComponent(batchId)}`);
}

export async function reportSuspicious({ batchId, location, notes, photoHash, pharmacyName }) {
  return publicPost("/public/report", { batchId, location, notes, photoHash, pharmacyName });
}
