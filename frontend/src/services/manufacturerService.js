import { apiGet, apiPost } from "../lib/api";
import { refreshBatches } from "./db";

export async function listInbox(manufacturerId) {
  return apiGet("/manufacturer/inbox");
}

export async function scheduleFacility(batchIds, facilityId, date, actor) {
  const res = await apiPost("/manufacturer/schedule", { batchIds, facilityId, date });
  await refreshBatches();
  return res;
}

// Certificate binding enforcement: cannot upload unless distributor-
// confirmed & forwarded. Stays a local pure pre-check over `batch.events`
// (BUILDPHASES.md — "called during render today"); the real enforcement is
// inside uploadCertificate below regardless.
export function certEligibility(batch) {
  if (!batch) return { eligible: false, reason: "Batch not found" };
  const confirmed = batch.events.some((e) => ["DISTRIBUTOR_CONFIRMED", "DISPUTE_RESOLVED"].includes(e.type));
  const forwarded = batch.events.some((e) => e.type === "FORWARDED");
  if (batch.status === "DESTROYED") return { eligible: false, reason: "Already destroyed" };
  if (!confirmed) return { eligible: false, reason: "This batch has not been confirmed at the distributor stage. Certificate upload blocked." };
  if (!forwarded) return { eligible: false, reason: "This batch has not been forwarded to the manufacturer yet. Certificate upload blocked." };
  return { eligible: true };
}

// Certificate binding enforcement is a real, thrown 409 for every
// ineligibility (`ALREADY_DESTROYED`, `NOT_DISTRIBUTOR_CONFIRMED`,
// `NOT_FORWARDED`, `CHAIN_HALTED_DISPUTE`) — never a soft 200. ARCHITECTURE.md
// §8.5 previously described a `{ok: false, reason}` 200 shape; that was the
// mismatch, resolved by updating the docs to match the real backend (§10's
// own error table already lists these as 409 cases) rather than reshaping a
// backend that already does the right thing. The caller
// (pages/manufacturer.jsx's CertUpload) catches the 409 itself via
// `onError` — the client-side `certEligibility` pre-check above already
// keeps this the rare/hostile-client path in practice.
export async function uploadCertificate(batchId, { certId, fileName }, actor) {
  const res = await apiPost("/manufacturer/certificates", { batchId, certId, fileName });
  await refreshBatches();
  return { ok: true, batch: res.batch, coveredBatches: res.coveredBatches };
}
