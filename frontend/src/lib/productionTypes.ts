export interface ProductionOrder {
  id: number;
  order_no: string;
  source_task_id: string;
  customer: string;
  project: string;
  due_date: string;
  sales_note: string;
  stage: string;
  status: string;
  shortage_status: string;
  cutting_started: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  owner?: string;
  producer?: string;
  planned_start?: string;
  planned_end?: string;
  task_snapshot?: Record<string, unknown>;
  quote_snapshot?: Record<string, unknown> | null;
  events?: ProductionEvent[];
  erpnext_sync?: ERPNextSync;
  erpnext_sync_status?: string;
  erpnext_sales_order?: string;
  erpnext_url?: string;
  erpnext_last_error?: string;
  erpnext_last_synced_at?: string;
}

export interface ERPNextSync {
  status: "待同步" | "同步中" | "已同步" | "同步失败";
  erpnext_customer: string;
  erpnext_item_code: string;
  erpnext_sales_order: string;
  erpnext_url: string;
  attempts: number;
  last_error: string;
  last_synced_at?: string | null;
}

export interface ERPNextBridgeStatus {
  enabled: boolean;
  configured: boolean;
  public_url: string;
  message: string;
}

export interface ERPNextConnectionStatus extends ERPNextBridgeStatus {
  connected: boolean;
}

export interface PendingProductionTask {
  task_id: string;
  source_revision: string;
  status: "待下达";
  customer: string;
  project: string;
  door_type: string;
  width: number | null;
  height: number | null;
  opening: string;
  approved_at: string;
  approved_by: string;
}

export interface ProductionTimelineItem {
  id: string;
  type: string;
  title: string;
  detail: string;
  operator: string;
  created_at: string;
}

export interface ProductionOrderFilters {
  stage?: string;
  status?: string;
  q?: string;
  owner?: string;
  shortage?: string;
  due_from?: string;
  due_to?: string;
}

export interface ProductionEvent {
  id: number;
  action: string;
  detail: string;
  operator_name: string;
  created_at: string;
}

export interface ProductionMaterial {
  id: number;
  code: string;
  name: string;
  category: string;
  material: string;
  specification: string;
  thickness: string;
  unit: string;
  supplier: string;
  warehouse_location: string;
  remark: string;
  active: number;
}

export interface BomItem {
  id?: number;
  material_id?: number | null;
  category: string;
  name: string;
  specification: string;
  material: string;
  thickness: string;
  quantity: number;
  unit: string;
  supply_type: string;
  remark: string;
}

export interface BomData {
  status: { status: string; published_at?: string | null };
  items: BomItem[];
}

export interface PurchaseItem {
  id?: number;
  order_id?: number | null;
  material_id?: number | null;
  requirement_item_id?: number | null;
  name: string;
  specification: string;
  quantity: number;
  received_quantity?: number;
  unit: string;
  unit_price: number;
  remark: string;
}

export interface PurchaseOrder {
  id: number;
  purchase_no: string;
  supplier: string;
  status: string;
  expected_date: string;
  remark: string;
  items: PurchaseItem[];
}

export interface InventoryBalance {
  material_id: number;
  code: string;
  name: string;
  unit: string;
  warehouse_location: string;
  quantity: number;
  specification: string;
  on_hand: number;
  reserved: number;
  available: number;
}

export interface MaterialRequirementItem {
  id: number;
  requirement_id: number;
  bom_item_id?: number | null;
  material_id?: number | null;
  material_code?: string | null;
  name: string;
  specification: string;
  required_quantity: number;
  reserved_quantity: number;
  purchased_quantity: number;
  received_quantity: number;
  issued_quantity: number;
  shortage_quantity: number;
  unit: string;
  status: string;
}

export interface MaterialRequirement {
  id: number;
  order_id: number;
  order_no: string;
  customer: string;
  project: string;
  due_date: string;
  shortage_status: string;
  status: string;
  created_at: string;
  updated_at: string;
  items: MaterialRequirementItem[];
}

export interface CuttingItem {
  id: number;
  name: string;
  specification: string;
  quantity: number;
  actual_quantity: number;
  unit: string;
  cutter: string;
  completed: number;
  remark: string;
}

export interface CuttingSheet {
  id: number;
  order_id: number;
  status: string;
  items: CuttingItem[];
}

export interface ProductionSchedule {
  order_id: number;
  planned_start: string;
  planned_end: string;
  producer: string;
  shortage_status: string;
  owner: string;
  allow_shortage?: boolean;
}

export interface ProductionOperation {
  id: number;
  sequence_no: number;
  name: string;
  status: string;
  operator_name: string;
  started_at?: string | null;
  completed_at?: string | null;
  remark: string;
}

export interface QualityInspection {
  id: number;
  result: string;
  inspector: string;
  return_operation: string;
  photos: string[];
  remark: string;
  created_at: string;
}

export interface FinishedGood {
  id: number;
  finished_no: string;
  order_id: number;
  order_no: string;
  customer: string;
  project: string;
  warehouse_location: string;
  status: string;
  inbound_at: string;
}

export interface Shipment {
  id: number;
  shipment_no: string;
  customer: string;
  project: string;
  address: string;
  contact: string;
  phone: string;
  logistics: string;
  tracking_no: string;
  status: string;
  remark: string;
  items: Array<{ order_id: number; order_no: string; finished_no: string }>;
}
