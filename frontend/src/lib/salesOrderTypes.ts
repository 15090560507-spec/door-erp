export interface SalesOrderQuoteChoice {
  quote_id: number;
  quote_date: string;
  updated_at: string;
  group_index: number;
  group_name: string;
  amount: number;
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
}

export interface SalesOrderLine {
  id: number;
  line_no: number;
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
}

export interface SalesOrder extends SalesOrderSummary {
  delivery_address: string;
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
  payment_nodes: SalesOrderPaymentNode[];
  events: Array<{ id: number; event_type: string; detail: string; operator: string; created_at: string }>;
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
}

export interface SalesOrderPayload {
  order_date: string;
  customer_name: string;
  project_name: string;
  delivery_address: string;
  salesperson: string;
  delivery_date: string;
  payment_template: string;
  remark: string;
  discount_amount: number;
  lines: SalesOrderLineInput[];
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
}

export type SalesOrderEditor = Omit<SalesOrderPayload, "lines"> & { lines: SalesOrderEditorLine[] };

export interface SalesOrderValidationWarning {
  key: string;
  message: string;
  lineNo?: number;
}
