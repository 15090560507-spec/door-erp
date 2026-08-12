import { api } from "./api";
import type {
  DoorUnitDetail,
  FulfillmentComponent,
  FulfillmentDashboard,
  FulfillmentOrder,
  FulfillmentWorkPackage,
  PendingFulfillmentTask,
  FulfillmentPerson,
} from "./fulfillmentTypes";

export async function getFulfillmentDashboard() {
  const { data } = await api.get<FulfillmentDashboard>("/fulfillment/dashboard");
  return data;
}

export async function getFulfillmentPeople() {
  const { data } = await api.get<{ people: FulfillmentPerson[] }>("/fulfillment/people");
  return data.people;
}

export async function getPendingFulfillmentTasks() {
  const { data } = await api.get<{ tasks: PendingFulfillmentTask[] }>("/fulfillment/pending-release");
  return data.tasks;
}

export async function releaseFulfillmentOrder(taskId: string, payload: { due_date: string; sales_note: string; door_count: number; owner_uid: string }) {
  const { data } = await api.post<{ order: FulfillmentOrder; message: string }>(`/fulfillment/orders/from-task/${taskId}`, payload);
  return data;
}

export async function getFulfillmentOrders(params?: { q?: string; status?: string }) {
  const { data } = await api.get<{ orders: FulfillmentOrder[] }>("/fulfillment/orders", { params });
  return data.orders;
}

export async function getFulfillmentOrder(id: number) {
  const { data } = await api.get<{ order: FulfillmentOrder }>(`/fulfillment/orders/${id}`);
  return data.order;
}

export async function getDoorUnit(id: number) {
  const { data } = await api.get<{ door_unit: DoorUnitDetail }>(`/fulfillment/door-units/${id}`);
  return data.door_unit;
}

export async function saveTechnicalPackage(doorId: number, payload: { product_summary: string; special_requirements: string; components: FulfillmentComponent[]; work_packages: FulfillmentWorkPackage[] }) {
  const { data } = await api.put<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/technical-package`, payload);
  return data;
}

export async function confirmTechnicalPackage(doorId: number) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/technical-package/confirm`);
  return data;
}

export async function updateFulfillmentWorkPackage(workId: number, payload: { status: string; executor_uid: string; actual_quantity?: number; remark: string }) {
  const { data } = await api.put<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/work-packages/${workId}`, payload);
  return data;
}

export async function createFulfillmentException(doorId: number, payload: { category: string; title: string; detail: string; severity: string; owner_uid: string }) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/exceptions`, payload);
  return data;
}

export async function resolveFulfillmentException(exceptionId: number, resolution: string) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/exceptions/${exceptionId}/resolve`, { resolution });
  return data;
}

export async function createFulfillmentChange(doorId: number, payload: { reason: string; impact_note: string }) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/changes`, payload);
  return data;
}

export async function updateFulfillmentSupply(supplyId: number, payload: { status: string; handler_uid: string; supplier: string; actual_quantity?: number; unit_cost?: number; remark: string }) {
  const { data } = await api.put<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/supplies/${supplyId}`, payload);
  return data;
}

export async function createFulfillmentInspection(doorId: number, payload: { inspection_type: string; result: string; target_name: string; quantity: number; defect_detail: string; remark: string }) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/inspections`, payload);
  return data;
}

export async function finishedFulfillmentInbound(doorId: number, payload: { warehouse: string; location: string; quantity: number; remark: string }) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/finished-inbound`, payload);
  return data;
}

export async function recordFulfillmentPayment(doorId: number, payload: { amount: number; payment_date: string; reference: string; remark: string }) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/payments`, payload);
  return data;
}

export async function createFulfillmentShipment(doorId: number, payload: { required_payment: number; carrier: string; vehicle_no: string; contact: string; authorization_reason: string; authorized_by: string; remark: string }) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/door-units/${doorId}/shipments`, payload);
  return data;
}

export async function signFulfillmentShipment(shipmentId: number, payload: { signed_by: string; signed_at: string; remark: string }) {
  const { data } = await api.post<{ door_unit: DoorUnitDetail; message: string }>(`/fulfillment/shipments/${shipmentId}/sign`, payload);
  return data;
}
