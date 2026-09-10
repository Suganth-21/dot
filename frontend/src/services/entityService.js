import { apiGet } from "../lib/api";

export async function listEntities() {
  return apiGet("/entities");
}

export async function getEntity(id) {
  return apiGet(`/entities/${encodeURIComponent(id)}`);
}
