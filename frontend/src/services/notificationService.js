import { apiGet, apiPatch } from "../lib/api";
import { patchNotificationsRead } from "./db";

export async function getNotifications(role) {
  return apiGet(`/notifications?role=${encodeURIComponent(role)}`);
}

export async function markAllRead(role) {
  patchNotificationsRead(role); // optimistic — instant bell update
  return apiPatch(`/notifications/read-all?role=${encodeURIComponent(role)}`, {});
}

export async function markRead(role, id) {
  patchNotificationsRead(role, id); // optimistic — instant bell update
  return apiPatch(`/notifications/${encodeURIComponent(id)}/read`, {});
}

// The client-side fake-notification generator is gone — notifications are
// server-created only, and the live feed now arrives via WebSocket
// `notification.created` (services/db.js). The export is kept as a no-op
// purely so App.js (not a services/*.js file in BUILDPHASES.md's table,
// and outside this task's edit list) doesn't need to drop its call site.
export function startNotificationSim() {}
