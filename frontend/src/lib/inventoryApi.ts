import { api } from "./api";
import type {
  AdjustmentItemPayload,
  InventoryBalance,
  InventoryMaterial,
  InventoryTransaction,
  InventoryWarehouse,
  MaterialRequirement,
  MaterialRequirementSummary,
  MaterialPayload,
} from "./inventoryTypes";

export async function getInventoryMaterials(params?: {
  q?: string;
  category?: string;
  material_type?: string;
  include_inactive?: boolean;
}) {
  const { data } = await api.get<{ materials: InventoryMaterial[] }>("/inventory/materials", { params });
  return data.materials;
}

export async function createInventoryMaterial(payload: MaterialPayload) {
  const { data } = await api.post<{ material: InventoryMaterial; message: string }>("/inventory/materials", payload);
  return data;
}

export async function updateInventoryMaterial(id: number, payload: MaterialPayload) {
  const { data } = await api.put<{ material: InventoryMaterial; message: string }>(`/inventory/materials/${id}`, payload);
  return data;
}

export async function getInventoryWarehouses() {
  const { data } = await api.get<{ warehouses: InventoryWarehouse[] }>("/inventory/warehouses");
  return data.warehouses;
}

export async function createInventoryWarehouse(payload: { code: string; name: string; warehouse_type: string; remark: string }) {
  const { data } = await api.post<{ warehouse: InventoryWarehouse; message: string }>("/inventory/warehouses", payload);
  return data;
}

export async function createInventoryLocation(warehouseId: number, payload: { code: string; name: string; remark: string }) {
  const { data } = await api.post<{ location: InventoryWarehouse["locations"][number]; message: string }>(`/inventory/warehouses/${warehouseId}/locations`, payload);
  return data;
}

export async function getInventoryBalances(params?: { q?: string; warehouse_id?: number; low_stock_only?: boolean }) {
  const { data } = await api.get<{ balances: InventoryBalance[] }>("/inventory/balances", { params });
  return data.balances;
}

export async function getInventoryTransactions(params?: { material_id?: number; limit?: number }) {
  const { data } = await api.get<{ transactions: InventoryTransaction[] }>("/inventory/transactions", { params });
  return data.transactions;
}

export async function createInventoryAdjustment(payload: { remark: string; items: AdjustmentItemPayload[] }) {
  const { data } = await api.post<{ adjustment: { id: number; document_no: string; status: string }; message: string }>("/inventory/adjustments", payload);
  return data;
}

export async function confirmInventoryAdjustment(id: number) {
  const { data } = await api.post<{ adjustment: { id: number; document_no: string; status: string }; message: string }>(`/inventory/adjustments/${id}/confirm`);
  return data;
}

export async function getMaterialRequirements(params?: { q?: string; status?: string }) {
  const { data } = await api.get<{ requirements: MaterialRequirementSummary[] }>("/inventory/requirements", { params });
  return data.requirements;
}

export async function getMaterialRequirement(id: number) {
  const { data } = await api.get<{ requirement: MaterialRequirement }>(`/inventory/requirements/${id}`);
  return data.requirement;
}

export async function reallocateMaterialRequirement(id: number) {
  const { data } = await api.post<{ requirement: MaterialRequirement; message: string }>(`/inventory/requirements/${id}/reallocate`);
  return data;
}

export async function supplementMaterialRequirement(itemId: number, payload: { material_id: number; quantity: number; remark: string }) {
  const { data } = await api.post<{ requirement: MaterialRequirement; message: string }>(`/inventory/requirement-items/${itemId}/supplement`, payload);
  return data;
}
