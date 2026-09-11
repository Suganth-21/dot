// Shared "what is this truck doing right now" logic for LiveMap vehicle
// markers — one place so the popup detail (status, origin pharmacy,
// drug/batch, quantity, ETA) reads identically on the distributor's and
// the manufacturer's fleet views, instead of drifting apart per page.

// A route can carry several stops (a multi-pharmacy pickup run); the one
// worth showing on a single vehicle marker is whichever is actively
// happening — current/arrived — or, once the whole run is done, the most
// recently completed one, so a just-finished pickup doesn't go blank.
export function activeStopOf(route) {
  return (
    route.stops.find((s) => s.status === "CURRENT" || s.status === "ARRIVED") ||
    [...route.stops].reverse().find((s) => s.status === "DONE") ||
    route.stops[0]
  );
}

export function vehicleDetailFor(route, stop) {
  if (!stop) return { pos: route.pos, reg: route.vehicleReg, agent: route.agentName, eta: route.etaMin };
  const picked = stop.status === "DONE";
  return {
    pos: route.pos, reg: route.vehicleReg, agent: route.agentName,
    // The drive-home leg (after pickup) is a real, GPS-simulated leg with
    // its own live ETA — it used to be hidden here (`picked ? null : ...`)
    // as if there were nothing left to time, which hid exactly the number
    // ("arriving at the distributor in X min") this is for.
    eta: route.etaMin,
    from: stop.pharmacyName,
    to: picked ? "distributor warehouse" : undefined,
    drugName: stop.drugName, batchId: stop.batchId,
    quantity: stop.counted ?? stop.quantityClaimed,
    statusLabel: picked ? "Picked up — heading back to distributor" : stop.status === "ARRIVED" ? "Arrived — collecting now" : "En route to pickup",
  };
}

// Manufacturer-only: which stop (if any) on this route carries a batch
// that's actually this manufacturer's — joined via `batches` (unscoped,
// carries manufacturerId), never `state.returns`: a manufacturer's
// return-read permission only opens up once a return is FORWARDED
// (ARCHITECTURE.md §6.5), long after pickup, so a return-based join would
// silently show nothing for every in-progress pickup.
export function myBatchStopOf(route, batches, manufacturerId) {
  return route.stops.find((s) => s.batchId && batches.find((b) => b.id === s.batchId)?.manufacturerId === manufacturerId);
}

// The distributor -> facility leg (FacilityRun) has one destination and a
// batch manifest instead of pharmacy stops, so its vehicle marker is built
// differently from a pickup route's — but ends up on the exact same
// LiveMap, same popup shape.
export function facilityRunVehicleDetail(run) {
  // `delivered` (not status/running) is the true signal — both "still en
  // route to the facility" and "delivered, now driving home" read as
  // running=true/status=active during the drive-home leg. See
  // FacilityRun.delivered's own docstring.
  const many = run.batches.length > 1;
  const totalQty = run.batches.reduce((sum, b) => sum + (b.quantity || 0), 0);
  return {
    pos: run.pos, reg: run.vehicleReg, agent: run.agentName,
    eta: run.delivered ? null : run.etaMin,
    to: run.facilityName,
    drugName: many ? `${run.batches.length} batches` : run.batches[0]?.drugName,
    batchId: many ? undefined : run.batches[0]?.batchId,
    quantity: totalQty || undefined,
    statusLabel: run.delivered ? "Delivered — awaiting destruction certificate" : "En route to facility",
  };
}

// Manufacturer-only: does this run carry any of this manufacturer's own
// batches — same batches-join reasoning as myBatchStopOf above.
export function myFacilityRunBatches(run, batches, manufacturerId) {
  return run.batches.filter((b) => batches.find((x) => x.id === b.batchId)?.manufacturerId === manufacturerId);
}
