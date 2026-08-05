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
  task_snapshot?: Record<string, unknown>;
  quote_snapshot?: Record<string, unknown> | null;
  events?: ProductionEvent[];
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
