import { api } from "./api";
import type {
  BomData,
  BomItem,
  CuttingSheet,
  FinishedGood,
  InventoryBalance,
  PendingProductionTask,
  ProductionMaterial,
  ProductionOperation,
  ProductionOrder,
  ProductionOrderFilters,
  ProductionSchedule,
  ProductionTimelineItem,
  PurchaseItem,
  PurchaseOrder,
  QualityInspection,
  Shipment,
} from "./productionTypes";

export async function getProductionDashboard() {
  const { data } = await api.get<{ counts: Record<string, number> }>("/production/dashboard");
  return data.counts;
}

export async function getProductionOrders(params?: ProductionOrderFilters) {
  const { data } = await api.get<{ orders: ProductionOrder[] }>("/production/orders", { params });
  return data.orders;
}

export async function getPendingProductionTasks() {
  const { data } = await api.get<{ tasks: PendingProductionTask[] }>("/production/pending-release");
  return data.tasks;
}

export async function getProductionOrder(id: number) {
  const { data } = await api.get<{ order: ProductionOrder }>(`/production/orders/${id}`);
  return data.order;
}

export async function getProductionTimeline(id: number) {
  const { data } = await api.get<{ timeline: ProductionTimelineItem[] }>(
    `/production/orders/${id}/timeline`,
  );
  return data.timeline;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function downloadProductionFile(path: string, filename: string) {
  const { data } = await api.get<Blob>(path, { responseType: "blob", timeout: 120000 });
  triggerBlobDownload(data, filename);
}

export async function openProductionPrint(path: string) {
  const printWindow = window.open("", "_blank");
  if (!printWindow) throw new Error("浏览器阻止了打印窗口，请允许本站打开新窗口");
  printWindow.document.write("<p style='font-family:sans-serif;padding:24px'>正在准备打印单据...</p>");
  try {
    const { data } = await api.get<string>(path, { responseType: "text", timeout: 120000 });
    const url = URL.createObjectURL(new Blob([data], { type: "text/html;charset=utf-8" }));
    printWindow.location.href = url;
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    printWindow.close();
    throw error;
  }
}

export async function releaseProductionOrder(taskId: string, payload: {
  due_date?: string;
  sales_note?: string;
  include_quote?: boolean;
  quote_id?: number;
}) {
  const { data } = await api.post<{ order: ProductionOrder; message: string }>(
    `/production/orders/from-task/${taskId}`,
    payload,
    { timeout: 120000 },
  );
  return data;
}

export async function copyProductionOrder(id: number, reason = "") {
  const { data } = await api.post(`/production/orders/${id}/copy`, { reason });
  return data;
}

export async function withdrawProductionOrder(id: number, reason = "") {
  const { data } = await api.post(`/production/orders/${id}/withdraw`, { reason });
  return data;
}

export async function orderAction(id: number, action: "pause" | "resume" | "void", reason = "") {
  const { data } = await api.post(`/production/orders/${id}/${action}`, { reason });
  return data;
}

export async function getProductionMaterials() {
  const { data } = await api.get<{ materials: ProductionMaterial[] }>("/production/materials");
  return data.materials;
}

export async function saveProductionMaterial(payload: Omit<ProductionMaterial, "id" | "active"> & { active?: boolean }, id?: number) {
  const { data } = id
    ? await api.put(`/production/materials/${id}`, payload)
    : await api.post("/production/materials", payload);
  return data.material as ProductionMaterial;
}

export async function disableProductionMaterial(id: number) {
  await api.delete(`/production/materials/${id}`);
}

export async function getBom(orderId: number) {
  const { data } = await api.get<BomData>(`/production/orders/${orderId}/bom`);
  return data;
}

export async function saveBom(orderId: number, items: BomItem[]) {
  const { data } = await api.put<BomData>(`/production/orders/${orderId}/bom`, { items });
  return data;
}

export async function publishBom(orderId: number) {
  const { data } = await api.post<BomData>(`/production/orders/${orderId}/bom/publish`);
  return data;
}

export async function getPurchases() {
  const { data } = await api.get<{ purchases: PurchaseOrder[] }>("/production/purchases");
  return data.purchases;
}

export async function createPurchase(payload: {
  supplier: string;
  expected_date: string;
  remark: string;
  items: PurchaseItem[];
}) {
  const { data } = await api.post("/production/purchases", payload);
  return data;
}

export async function setPurchaseStatus(id: number, status: string) {
  await api.put(`/production/purchases/${id}/status`, { status });
}

export async function receivePurchase(id: number, items: Array<{ item_id: number; quantity: number; warehouse_location: string }>) {
  const { data } = await api.post(`/production/purchases/${id}/receive`, { items });
  return data;
}

export async function getInventory() {
  const { data } = await api.get<{ balances: InventoryBalance[]; transactions: Record<string, unknown>[] }>("/production/inventory");
  return data;
}

export async function createInventoryTransaction(payload: Record<string, unknown>) {
  const { data } = await api.post("/production/inventory/transactions", payload);
  return data;
}

export async function getCuttingSheet(orderId: number) {
  const { data } = await api.get<{ sheet: CuttingSheet | null }>(`/production/orders/${orderId}/cutting-sheet`);
  return data.sheet;
}

export async function createCuttingSheet(orderId: number) {
  const { data } = await api.post<{ sheet: CuttingSheet }>(`/production/orders/${orderId}/cutting-sheet`);
  return data.sheet;
}

export async function saveCuttingSheet(orderId: number, sheet: CuttingSheet) {
  const { data } = await api.put<{ sheet: CuttingSheet }>(`/production/orders/${orderId}/cutting-sheet`, {
    status: sheet.status,
    items: sheet.items.map((item) => ({
      id: item.id,
      actual_quantity: Number(item.actual_quantity || 0),
      cutter: item.cutter,
      completed: Boolean(item.completed),
      remark: item.remark,
    })),
  });
  return data.sheet;
}

export async function getSchedule(orderId: number) {
  const { data } = await api.get<{ schedule: ProductionSchedule | null }>(`/production/orders/${orderId}/schedule`);
  return data.schedule;
}

export async function saveSchedule(orderId: number, schedule: Omit<ProductionSchedule, "order_id">) {
  const { data } = await api.put(`/production/orders/${orderId}/schedule`, schedule);
  return data.schedule as ProductionSchedule;
}

export async function getOperations(orderId: number) {
  const { data } = await api.get<{ operations: ProductionOperation[] }>(`/production/orders/${orderId}/operations`);
  return data.operations;
}

export async function saveOperation(orderId: number, operationId: number, payload: { status: string; operator_name: string; remark: string }) {
  const { data } = await api.put<{ operations: ProductionOperation[] }>(
    `/production/orders/${orderId}/operations/${operationId}`,
    payload,
  );
  return data.operations;
}

export async function getQuality(orderId: number) {
  const { data } = await api.get<{ inspections: QualityInspection[] }>(`/production/orders/${orderId}/quality`);
  return data.inspections;
}

export async function createQuality(orderId: number, payload: {
  result: string;
  inspector: string;
  return_operation: string;
  photos: string[];
  remark: string;
}) {
  const { data } = await api.post(`/production/orders/${orderId}/quality`, payload);
  return data.inspections as QualityInspection[];
}

export async function getFinishedGoods() {
  const { data } = await api.get<{ finished_goods: FinishedGood[] }>("/production/finished-goods");
  return data.finished_goods;
}

export async function inboundFinishedGood(orderId: number, warehouseLocation: string) {
  const { data } = await api.post(`/production/orders/${orderId}/finished-goods/inbound`, {
    warehouse_location: warehouseLocation,
  });
  return data.finished_good as FinishedGood;
}

export async function getShipments() {
  const { data } = await api.get<{ shipments: Shipment[] }>("/production/shipments");
  return data.shipments;
}

export async function createShipment(payload: Record<string, unknown>) {
  const { data } = await api.post("/production/shipments", payload);
  return data;
}

export async function setShipmentStatus(id: number, status: string, trackingNo = "", remark = "") {
  await api.put(`/production/shipments/${id}/status`, { status, tracking_no: trackingNo, remark });
}
