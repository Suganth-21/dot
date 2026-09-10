import { getState, mutate } from "./db";
import { appendEvent } from "./batchService";
import { notify } from "./notificationService";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

export async function listInbox(manufacturerId) {
  await delay();
  const s = getState();
  // returns forwarded whose batch belongs to this manufacturer & not yet scheduled/destroyed
  return s.returns
    .filter((r) => r.status === "FORWARDED")
    .map((r) => {
      const batch = s.batches.find((b) => b.id === r.batchId);
      return { ...r, batch };
    })
    .filter((r) => r.batch && (!manufacturerId || r.batch.manufacturerId === manufacturerId) && r.batch.status !== "DESTROYED");
}

export async function scheduleFacility(batchIds, facilityId, date, actor) {
  await delay();
  mutate((s) => {
    const fac = s.facilities.find((f) => f.id === facilityId);
    batchIds.forEach((id) => {
      const batch = s.batches.find((b) => b.id === id);
      if (!batch) return;
      batch.scheduledFacility = { id: facilityId, name: fac?.name, date };
      appendEvent(batch, "FACILITY_SCHEDULED", actor, { facility: fac?.name, date });
    });
  });
  return { ok: true };
}

// Certificate binding enforcement: cannot upload unless distributor-confirmed & forwarded.
export function certEligibility(batch) {
  if (!batch) return { eligible: false, reason: "Batch not found" };
  const confirmed = batch.events.some((e) => ["DISTRIBUTOR_CONFIRMED", "DISPUTE_RESOLVED"].includes(e.type));
  const forwarded = batch.events.some((e) => e.type === "FORWARDED");
  if (batch.status === "DESTROYED") return { eligible: false, reason: "Already destroyed" };
  if (!confirmed) return { eligible: false, reason: "This batch has not been confirmed at the distributor stage. Certificate upload blocked." };
  if (!forwarded) return { eligible: false, reason: "This batch has not been forwarded to the manufacturer yet. Certificate upload blocked." };
  return { eligible: true };
}

export async function uploadCertificate(batchId, { certId, fileName }, actor) {
  await delay(300);
  let result = null;
  mutate((s) => {
    const batch = s.batches.find((b) => b.id === batchId);
    if (!batch) return;
    const elig = certEligibility(batch);
    if (!elig.eligible) {
      result = { ok: false, reason: elig.reason };
      return;
    }
    batch.status = "DESTROYED";
    batch.destroyed = true;
    batch.destroyedDate = new Date().toISOString();
    batch.certId = certId || `CERT-${batch.code}-2026`;
    const fac = batch.scheduledFacility;
    batch.holder = { type: "FACILITY", id: fac?.id, name: fac?.name || "Licensed facility" };
    appendEvent(batch, "DESTROYED", actor, { facility: fac?.name, certId: batch.certId, fileName });
    notify("REGULATOR", "Batch destroyed", `${batch.drugName} (${batch.id}) destruction certificate uploaded`, "success", `/regulator/batches/${batch.id}`);
    notify("RETAILER", "Return closed", `${batch.drugName} was destroyed and verified`, "success");
    result = { ok: true, batch: { ...batch }, coveredBatches: [batch.id] };
  });
  return result;
}
