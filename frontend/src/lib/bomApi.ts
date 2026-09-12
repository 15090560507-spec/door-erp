import { api } from "./api";
import type { BomDetail, BomDraftItem, BomWorkbenchResponse } from "./bomTypes";

type BomResult = { bom: BomDetail; message?: string };

export async function getBomWorkbench(params?: { q?: string; status?: string; page?: number; page_size?: number }) {
  const { data } = await api.get<BomWorkbenchResponse>("/bom/workbench", { params });
  return data;
}

export async function getDoorBom(doorUnitId: number, version?: number) {
  const { data } = await api.get<{ bom: BomDetail }>(`/bom/door-units/${doorUnitId}`, { params: version ? { version } : undefined });
  return data.bom;
}

export async function generateDoorBom(doorUnitId: number) {
  const { data } = await api.post<BomResult>(`/bom/door-units/${doorUnitId}/generate`);
  return data;
}

export async function saveDoorBomDraft(doorUnitId: number, payload: { items: BomDraftItem[]; product_summary?: string; special_requirements?: string }) {
  const { data } = await api.put<BomResult>(`/bom/door-units/${doorUnitId}/draft`, payload);
  return data;
}

export async function verifyDoorBomRows(doorUnitId: number, itemIds: number[]) {
  const { data } = await api.post<BomResult>(`/bom/door-units/${doorUnitId}/verify`, { item_ids: itemIds });
  return data;
}

export async function publishDoorBom(doorUnitId: number, remark = "") {
  const { data } = await api.post<BomResult & { idempotent: boolean }>(`/bom/door-units/${doorUnitId}/publish`, { remark });
  return data;
}

export async function createDoorBomVersion(doorUnitId: number, reason: string, impactNote = "") {
  const { data } = await api.post<BomResult>(`/bom/door-units/${doorUnitId}/new-version`, { reason, impact_note: impactNote });
  return data;
}
