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
  PurchaseOrder,
  PurchaseReceipt,
  PurchaseShortage,
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

export async function getPurchaseShortages(q = "") {
  const { data } = await api.get<{ shortages: PurchaseShortage[] }>("/inventory/purchasing/shortages", { params: { q } });
  return data.shortages;
}

export async function getPurchaseOrders(params?: { q?: string; status?: string }) {
  const { data } = await api.get<{ orders: PurchaseOrder[] }>("/inventory/purchasing/orders", { params });
  return data.orders;
}

export async function getPurchaseOrder(id: number) {
  const { data } = await api.get<{ order: PurchaseOrder }>(`/inventory/purchasing/orders/${id}`);
  return data.order;
}

export async function createPurchaseOrder(payload: {
  supplier: string;
  expected_date: string;
  remark: string;
  items: Array<{
    material_id: number;
    quantity: number;
    unit: string;
    unit_price: number;
    remark: string;
    allocations: Array<{ requirement_item_id: number; quantity: number }>;
  }>;
}) {
  const { data } = await api.post<{ order: PurchaseOrder; message: string }>("/inventory/purchasing/orders", payload);
  return data;
}

export async function confirmPurchaseOrder(id: number) {
  const { data } = await api.post<{ order: PurchaseOrder; message: string }>(`/inventory/purchasing/orders/${id}/confirm`);
  return data;
}

export async function cancelPurchaseOrder(id: number) {
  const { data } = await api.post<{ order: PurchaseOrder; message: string }>(`/inventory/purchasing/orders/${id}/cancel`);
  return data;
}

export async function createPurchaseReceipt(orderId: number, payload: {
  arrival_date: string;
  remark: string;
  items: Array<{ purchase_order_item_id: number; quantity: number }>;
}) {
  const { data } = await api.post<{ receipt: PurchaseReceipt; message: string }>(`/inventory/purchasing/orders/${orderId}/receipts`, payload);
  return data;
}

export async function getPurchaseReceipts(status = "") {
  const { data } = await api.get<{ receipts: PurchaseReceipt[] }>("/inventory/receipts", { params: { status } });
  return data.receipts;
}

export async function getPurchaseReceipt(id: number) {
  const { data } = await api.get<{ receipt: PurchaseReceipt }>(`/inventory/receipts/${id}`);
  return data.receipt;
}

export async function inspectPurchaseReceiptItem(id: number, payload: {
  qualified_quantity: number;
  concession_quantity: number;
  rejected_quantity: number;
  warehouse_id: number;
  location_id: number;
  remark: string;
}) {
  const { data } = await api.post<{ receipt: PurchaseReceipt; message: string }>(`/inventory/receipt-items/${id}/inspect`, payload);
  return data;
}
