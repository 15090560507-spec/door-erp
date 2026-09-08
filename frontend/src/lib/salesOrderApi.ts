import { api } from "./api";
import type {
  SalesOrder,
  SalesOrderCandidate,
  SalesOrderPayload,
  SalesOrderSummary,
} from "./salesOrderTypes";

export async function getSalesOrderCandidates(params?: {
  q?: string;
  customer?: string;
  project?: string;
  door_type?: string;
  width?: number;
  height?: number;
  quote_state?: "已报价" | "未报价";
  final_review_from?: string;
  final_review_to?: string;
  page?: number;
  page_size?: number;
  current_order_id?: number;
}) {
  const { data } = await api.get<{ candidates: SalesOrderCandidate[]; total: number; page: number; page_size: number }>("/sales-orders/candidates", { params });
  return data.candidates;
}

export async function getSalesOrders(params?: { q?: string; status?: string }) {
  const { data } = await api.get<{ orders: SalesOrderSummary[]; total: number }>("/sales-orders", { params });
  return data.orders;
}

export async function getSalesOrder(orderId: number) {
  const { data } = await api.get<{ order: SalesOrder }>(`/sales-orders/${orderId}`);
  return data.order;
}

export async function createSalesOrder(payload: SalesOrderPayload) {
  const { data } = await api.post<{ order: SalesOrder; message: string }>("/sales-orders", payload);
  return data;
}

export async function updateSalesOrder(orderId: number, payload: SalesOrderPayload) {
  const { data } = await api.put<{ order: SalesOrder; message: string }>(`/sales-orders/${orderId}`, payload);
  return data;
}

export async function confirmSalesOrder(orderId: number) {
  const { data } = await api.post<{ order: SalesOrder; message: string }>(`/sales-orders/${orderId}/confirm`);
  return data;
}

export async function cancelSalesOrder(orderId: number, reason: string) {
  const { data } = await api.post<{ order: SalesOrder; message: string }>(`/sales-orders/${orderId}/cancel`, { reason });
  return data;
}

export async function retrySalesOrderProvisioning(orderId: number) {
  const { data } = await api.post<{ order: SalesOrder; message: string }>(`/sales-orders/${orderId}/retry-provisioning`);
  return data;
}
