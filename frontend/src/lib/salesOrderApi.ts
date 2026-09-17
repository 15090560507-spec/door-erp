import { api } from "./api";
import type {
  SalesOrder,
  SalesOrderCandidate,
  SalesOrderPayload,
  SalesOrderReceipt,
  SalesOrderReceiptCandidate,
  SalesOrderSummary,
  SalesOrderAttachment,
  SalesOrderSuggestions,
} from "./salesOrderTypes";

export type SalesOrderCandidateFilters = {
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
};

export async function getSalesOrderCandidates(params?: SalesOrderCandidateFilters): Promise<SalesOrderCandidate[]> {
  const { data } = await api.get<{ candidates: SalesOrderCandidate[]; total: number; page: number; page_size: number }>("/sales-orders/candidates", { params });
  return data.candidates;
}

export async function getSalesOrders(params?: { q?: string; status?: string }): Promise<SalesOrderSummary[]> {
  const { data } = await api.get<{ orders: SalesOrderSummary[]; total: number }>("/sales-orders", { params });
  return data.orders;
}

export async function getSalesOrderSuggestions(): Promise<SalesOrderSuggestions> {
  const { data } = await api.get<SalesOrderSuggestions>("/sales-orders/suggestions");
  return data;
}

export async function uploadSalesOrderAttachments(orderId: number, category: SalesOrderAttachment["category"], files: File[]) {
  const form = new FormData();
  form.append("category", category);
  files.forEach((file) => form.append("files", file));
  const { data } = await api.post<{ attachments: SalesOrderAttachment[]; message: string }>(`/sales-orders/${orderId}/attachments`, form);
  return data;
}

export async function deleteSalesOrderAttachment(orderId: number, attachmentId: number) {
  const { data } = await api.delete<{ message: string }>(`/sales-orders/${orderId}/attachments/${attachmentId}`);
  return data;
}

export async function getSalesOrder(orderId: number): Promise<SalesOrder> {
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

export async function getSalesOrderReceiptCandidates(customer: string): Promise<SalesOrderReceiptCandidate[]> {
  const { data } = await api.get<{ orders: SalesOrderReceiptCandidate[] }>("/sales-orders/receipt-candidates", { params: { customer } });
  return data.orders;
}

export async function createSalesOrderReceipt(payload: {
  receipt_date: string;
  amount: number;
  payment_method: string;
  reference: string;
  remark: string;
  allocations: Array<{ order_id: number; amount: number }>;
}) {
  const { data } = await api.post<{ receipt: SalesOrderReceipt; message: string }>("/sales-orders/receipts", payload);
  return data;
}

export async function reverseSalesOrderReceipt(receiptId: number, reason: string) {
  const { data } = await api.post<{ receipt: SalesOrderReceipt; message: string }>(`/sales-orders/receipts/${receiptId}/reverse`, { reason });
  return data;
}
