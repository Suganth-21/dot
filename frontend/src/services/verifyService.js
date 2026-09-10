import { getState, mutate } from "./db";
import { uid } from "../lib/utils";
import { pushAlert } from "./alertService";
import { notify } from "./notificationService";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

// Public Patient Shield verification — no auth.
export async function verifyBatch(batchId) {
  await delay(300);
  const s = getState();
  const batch = s.batches.find((b) => b.id === batchId || b.code === batchId || b.id === `BATCH-${batchId}`);
  if (!batch) {
    return { verdict: "NOT_FOUND", batchId };
  }
  if (batch.status === "DESTROYED") {
    const destroyEvt = batch.events.find((e) => e.type === "DESTROYED");
    return {
      verdict: "DESTROYED",
      batch: {
        id: batch.id, drugName: batch.drugName, manufacturerName: batch.manufacturerName,
        expiryDate: batch.expiryDate, destroyedDate: batch.destroyedDate || destroyEvt?.ts, certId: batch.certId,
      },
      history: batch.events.slice(-5).map((e) => ({ type: e.type, ts: e.ts })),
    };
  }
  return {
    verdict: "GENUINE",
    batch: {
      id: batch.id, drugName: batch.drugName, manufacturerName: batch.manufacturerName,
      expiryDate: batch.expiryDate, status: batch.status,
    },
  };
}

export async function reportSuspicious({ batchId, location, notes, photoHash, pharmacyName }) {
  await delay(200);
  let report = null;
  mutate((s) => {
    report = {
      id: uid("prep"),
      batchId,
      location,
      notes,
      photoHash,
      pharmacyName,
      ts: new Date().toISOString(),
    };
    s.patientReports.unshift(report);
    const batch = s.batches.find((b) => b.id === batchId);
    const alert = pushAlert({
      type: "PATIENT_REPORT",
      severity: batch && batch.status === "DESTROYED" ? "critical" : "high",
      batchId: batchId || "UNKNOWN",
      drugName: batch?.drugName || "Unknown drug",
      drugCategory: batch?.category || "other",
      entityId: "public",
      entityName: pharmacyName || "Reported by patient",
      district: location?.district || "Unknown",
      manufacturerId: batch?.manufacturerId,
      rule: "Public report via Patient Shield",
      message: `PATIENT REPORT: Suspicious medicine reported${batchId ? ` — ${batchId}` : ""}${notes ? ` (${notes})` : ""}`,
    });
    notify("REGULATOR", "New patient report", alert.message, "danger", `/regulator/alerts/${alert.id}`);
  });
  return report;
}
