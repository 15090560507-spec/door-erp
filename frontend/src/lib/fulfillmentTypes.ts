export interface PendingFulfillmentTask {
  task_id: string;
  source_revision: string;
  status: "待下达";
  customer: string;
  project: string;
  product_name: string;
  door_type: string;
  width: number | null;
  height: number | null;
  opening: string;
  approved_at: string;
  approved_by: string;
}

export interface FulfillmentOrder {
  id: number;
  order_no: string;
  customer: string;
  project: string;
  due_date: string;
  sales_note: string;
  status: string;
  created_by: string;
  created_at: string;
  door_count: number;
  completed_count: number;
  representative_status: string;
  progress: number;
  door_units?: DoorUnitSummary[];
}

export interface DoorUnitSummary {
  id: number;
  order_id: number;
  production_no: string;
  sequence_no: number;
  product_name: string;
  specification: string;
  opening: string;
  due_date: string;
  owner_uid: string;
  technical_uid: string;
  status: string;
  progress: number;
  active_version: number;
  risk_tags: string[];
}

export interface FulfillmentComponent {
  id?: number;
  parent_id?: number | null;
  name: string;
  category: string;
  specification: string;
  quantity: number;
  unit: string;
  acquisition_method: string;
  remark: string;
}

export interface FulfillmentWorkPackage {
  id?: number;
  component_id?: number | null;
  name: string;
  category: string;
  route: string;
  acquisition_method: string;
  executor_uid: string;
  planned_start: string;
  planned_end: string;
  opening_condition: string;
  blocking_node: string;
  quantity: number;
  actual_quantity?: number;
  unit: string;
  piece_rate: number;
  inspection_required: number | boolean;
  status?: string;
  remark: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface TechnicalPackage {
  id: number;
  version: number;
  status: "草稿" | "已确认";
  product_summary: string;
  special_requirements: string;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  components: FulfillmentComponent[];
  work_packages: FulfillmentWorkPackage[];
}

export interface FulfillmentException {
  id: number;
  category: string;
  title: string;
  detail: string;
  severity: string;
  owner_uid: string;
  status: string;
  resolution: string;
  created_at: string;
}

export interface FulfillmentEvent {
  id: number;
  action: string;
  detail: string;
  operator_name: string;
  created_at: string;
}

export interface FulfillmentChange {
  id: number;
  change_no: string;
  from_version: number;
  to_version: number;
  reason: string;
  impact_note: string;
  status: string;
  created_at: string;
}

export interface FulfillmentSupply {
  id: number; name: string; category: string; specification: string;
  required_quantity: number; actual_quantity: number; unit: string;
  acquisition_method: string; handler_uid: string; supplier: string;
  unit_cost: number; status: string; remark: string;
}

export interface FulfillmentWorkbenchSupply extends FulfillmentSupply {
  door_unit_id: number;
  production_no: string;
  door_status: string;
  order_no: string;
  customer: string;
  project: string;
  inspection_passed: number;
}

export interface FulfillmentInspection {
  id: number; inspection_type: string; target_name: string; quantity: number;
  result: string; defect_detail: string; remark: string; inspector_uid: string; created_at: string;
}

export interface InventoryMovement {
  id: number; movement_type: string; item_name: string; warehouse: string;
  location: string; quantity: number; unit: string; remark: string; created_at: string;
}

export interface FulfillmentShipment {
  id: number; required_payment: number; paid_amount: number; authorized: number;
  authorization_reason: string; authorized_by: string; carrier: string;
  vehicle_no: string; contact: string; status: string; remark: string;
  created_at: string; signed_by: string; signed_at?: string | null;
}

export interface PayrollDraft {
  id: number; employee_uid: string; work_name: string; quantity: number;
  piece_rate: number; amount: number; status: string;
}

export interface DoorUnitDetail extends DoorUnitSummary {
  order_no: string;
  customer: string;
  project: string;
  sales_note: string;
  technical_package: TechnicalPackage;
  exceptions: FulfillmentException[];
  events: FulfillmentEvent[];
  changes: FulfillmentChange[];
  supplies: FulfillmentSupply[];
  inspections: FulfillmentInspection[];
  inventory_movements: InventoryMovement[];
  shipments: FulfillmentShipment[];
  payroll_drafts: PayrollDraft[];
  unfinished_work_packages: Array<{ id: number; name: string; status: string }>;
  paid_amount: number;
  allocated_payment: number;
  available_payment: number;
}

export interface FulfillmentDashboard {
  status_counts: Record<string, number>;
  pending_release: number;
  open_exceptions: number;
  due_risks: number;
}

export interface FulfillmentPerson {
  uid: string;
  name: string;
  role: string;
}
