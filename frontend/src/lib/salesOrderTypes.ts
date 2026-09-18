export interface SalesOrderQuoteChoice {
  quote_id: number;
  quote_date: string;
  updated_at: string;
  group_index: number;
  group_name: string;
  amount: number;
  pricing_mode?: string;
  items?: SalesOrderQuoteItem[];
}

export interface SalesOrderQuoteItem {
  productName: string;
  width?: number | null;
  height?: number | null;
  quantity?: number | null;
  unit?: string;
  unitPrice?: number;
  category?: string;
  specification?: string;
  model?: string;
  remark?: string;
}

export type SalesOrderStatus = "draft" | "confirmed" | "fulfilling" | "completed" | "cancelled";
export type SalesOrderProvisioningStatus = "not_started" | "pending" | "processing" | "ready" | "failed";

export interface SalesOrderCandidate {
  task_id: string;
  customer_name: string;
  project_name: string;
  product_name: string;
  door_type: string;
  width: number;
  height: number;
  opening_direction: string;
  color: string;
  drawing_status: string;
  approved_at: string;
  quote_status: string;
  quotes: SalesOrderQuoteChoice[];
  technical_details: SalesOrderTechnicalDetails;
}

export interface SalesOrderTechnicalDetails {
  trim_type: string;
  main_door_style: string;
  lock_type: string;
  handle: string;
  hinge: string;
  material: string;
  item_remark: string;
}

export interface SalesOrderAttachment {
  id: number;
  sales_order_id: number;
  category: "door_drawing" | "customer_signed" | "quote_signed" | "split_drawing";
  original_name: string;
  mime_type: string;
  file_size: number;
  uploaded_by: string;
  created_at: string;
}

export interface SalesOrderLine extends Partial<SalesOrderTechnicalDetails> {
  id: number;
  line_no: number;
  line_code: string;
  source_type: "drawing" | "manual";
  task_id: string;
  quote_id: number | null;
  quote_group_index: number | null;
  product_name: string;
  door_type: string;
  width: number;
  height: number;
  opening_direction: string;
  color: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
  drawing_status: string;
  current_drawing_status?: string;
  drawing_revision: string;
  source_changed?: boolean;
  quote_choices?: SalesOrderQuoteChoice[];
  drawing_snapshot?: { params?: Record<string, unknown> };
  remark: string;
  technical_details: SalesOrderTechnicalDetails;
}

export interface SalesOrderChargeLine {
  id?: number;
  door_line_no: number | null;
  source_type: "quote" | "manual";
  quote_item_index?: number | null;
  item_type: string;
  product_name: string;
  specification: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount?: number;
  pricing_mode: string;
  remark: string;
}

export interface SalesOrderPaymentNode {
  id?: number;
  name: string;
  due_percent: number;
  due_amount: number;
  planned_date: string;
  paid_amount?: number;
  paid_date?: string;
  status?: string;
  remark: string;
}

export interface SalesOrderReceiptCandidate {
  id: number;
  order_no: string;
  customer_name: string;
  project_name: string;
  order_date: string;
  total_amount: number;
  paid_amount: number;
  unpaid_amount: number;
}

export interface SalesOrderReceipt {
  id: number;
  receipt_no: string;
  customer_name: string;
  receipt_date: string;
  amount: number;
  allocation_amount?: number;
  payment_method: string;
  reference: string;
  remark: string;
  status: "confirmed" | "reversed";
  created_by: string;
  created_at: string;
  reversed_by?: string;
  reversed_at?: string | null;
  allocations?: Array<{ id: number; order_id: number; order_no: string; project_name: string; amount: number }>;
}

export interface SalesOrderSummary {
  id: number;
  order_no: string;
  order_date: string;
  customer_name: string;
  project_name: string;
  delivery_date: string;
  status: string;
  total_amount: number;
  line_count: number;
  door_count: number;
  releasable_count: number;
  updated_at: string;
  provisioning_status?: SalesOrderProvisioningStatus;
  provisioning_error?: string;
  fulfillment_order_id?: number | null;
  paid_amount?: number;
  unpaid_amount?: number;
  first_door_type?: string;
  first_product_name?: string;
  first_width?: number;
  first_height?: number;
}

export interface SalesOrder extends SalesOrderSummary {
  delivery_address: string;
  customer_phone: string;
  product_category: string;
  salesperson: string;
  payment_template: string;
  remark: string;
  subtotal: number;
  discount_amount: number;
  version: number;
  created_by: string;
  created_at: string;
  confirmed_at: string | null;
  cancel_reason: string;
  lines: SalesOrderLine[];
  charge_lines: SalesOrderChargeLine[];
  payment_nodes: SalesOrderPaymentNode[];
  receipts: SalesOrderReceipt[];
  paid_amount: number;
  unpaid_amount: number;
  events: Array<{ id: number; event_type: string; detail: string; operator: string; created_at: string }>;
  attachments: SalesOrderAttachment[];
}

export interface SalesOrderLineInput {
  source_type?: "drawing" | "manual";
  task_id?: string;
  quote_id?: number | null;
  quote_group_index?: number | null;
  product_name?: string;
  door_type?: string;
  width?: number | null;
  height?: number | null;
  opening_direction?: string;
  color?: string;
  quantity: number;
  unit?: string;
  unit_price?: number | null;
  remark: string;
  technical_details?: Partial<SalesOrderTechnicalDetails>;
}

export interface SalesOrderPayload {
  order_date: string;
  customer_name: string;
  project_name: string;
  delivery_address: string;
  customer_phone: string;
  product_category: string;
  salesperson: string;
  delivery_date: string;
  payment_template: string;
  remark: string;
  discount_amount: number;
  lines: SalesOrderLineInput[];
  charge_lines: SalesOrderChargeLine[];
  payment_nodes: SalesOrderPaymentNode[];
}

export interface SalesOrderEditorLine {
  source_type: "drawing" | "manual";
  task_id: string;
  product_name: string;
  door_type: string;
  width: number;
  height: number;
  opening_direction: string;
  color: string;
  drawing_status: string;
  drawing_revision?: string;
  source_approved_at?: string;
  quote_id: number | null;
  quote_group_index: number | null;
  quoteChoices: SalesOrderQuoteChoice[];
  quantity: number;
  unit: string;
  unit_price: number;
  remark: string;
  source_changed?: boolean;
  technical_details: SalesOrderTechnicalDetails;
}

export interface SalesOrderSuggestions {
  customer_name: string[];
  project_name: string[];
  delivery_address: string[];
  customer_phone: string[];
  product_category: string[];
}

export type SalesOrderEditor = Omit<SalesOrderPayload, "lines"> & { lines: SalesOrderEditorLine[] };

export interface SalesOrderValidationWarning {
  key: string;
  message: string;
  lineNo?: number;
}
