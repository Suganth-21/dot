// Batch QR payloads.
//
// A DOT-generated label (QrCodeGenerator) encodes the FULL batch record as
// JSON, not just the batch id — so a scan on the receiving end (a pharmacy
// adding stock, a checkout scan, /verify) can autofill everything instead of
// forcing a human to re-key drug/manufacturer/dates by hand. Old/demo/manual
// codes are still plain batch-id strings (e.g. "BATCH-DOX-2026-A17"); decode
// stays permissive so both keep working through the exact same scanner.

export function encodeBatchQr(batch) {
  return JSON.stringify({
    v: 1,
    batchId: batch.batchId,
    drugName: batch.drugName,
    drugKey: batch.drugKey,
    category: batch.category,
    manufacturerName: batch.manufacturerName,
    manufacturerId: batch.manufacturerId,
    mfg: batch.mfg,
    exp: batch.exp,
    quantity: batch.quantity,
    unitPrice: batch.unitPrice,
  });
}

// Always returns at least { batchId }. Extra fields are only present when
// the scanned code was a DOT-generated JSON payload.
export function decodeBatchQr(raw) {
  if (typeof raw !== "string") return { batchId: raw };
  const trimmed = raw.trim();
  if (trimmed.startsWith("{")) {
    try {
      const obj = JSON.parse(trimmed);
      if (obj && obj.batchId) return obj;
    } catch {
      // Not JSON — fall through and treat the whole string as a plain batch id.
    }
  }
  return { batchId: trimmed };
}
