export interface InventoryLocation {
  id: number;
  warehouse_id: number;
  code: string;
  name: string;
  is_active: number;
  remark: string;
}

export interface InventoryWarehouse {
  id: number;
  code: string;
  name: string;
  warehouse_type: string;
  is_active: number;
  remark: string;
  locations: InventoryLocation[];
}

export interface InventoryMaterial {
  id: number;
  code: string;
  name: string;
  category: string;
  specification: string;
  unit: string;
  material_type: string;
  default_warehouse_id?: number | null;
  default_location_id?: number | null;
  default_warehouse_name?: string;
  default_location_name?: string;
  default_supplier: string;
  minimum_stock: number;
  is_active: number;
  remark: string;
}

export interface InventoryBalance {
  material_id: number;
  warehouse_id: number;
  location_id: number;
  material_code: string;
  material_name: string;
  category: string;
  specification: string;
  unit: string;
  material_type: string;
  minimum_stock: number;
  warehouse_code: string;
  warehouse_name: string;
  location_code: string;
  location_name: string;
  on_hand: number;
  reserved: number;
  available: number;
  purchase_in_transit: number;
  subcontract_in_transit: number;
  updated_at: string;
}

export interface InventoryTransaction {
  id: number;
  material_id: number;
  material_code: string;
  material_name: string;
  warehouse_name: string;
  location_name: string;
  transaction_type: string;
  quantity: number;
  unit: string;
  source_type: string;
  source_id: string;
  source_line: string;
  production_no: string;
  operator_uid: string;
  remark: string;
  created_at: string;
}

export interface MaterialPayload {
  code: string;
  name: string;
  category: string;
  specification: string;
  unit: string;
  material_type: string;
  default_warehouse_id?: number | null;
  default_location_id?: number | null;
  default_supplier: string;
  minimum_stock: number;
  remark: string;
  is_active?: boolean;
}

export interface AdjustmentItemPayload {
  material_id: number;
  warehouse_id: number;
  location_id: number;
  quantity: number;
  unit: string;
  remark: string;
}

export interface MaterialRequirementSummary {
  id: number;
  requirement_no: string;
  order_id: number;
  door_unit_id: number;
  technical_package_id: number;
  production_no: string;
  version: number;
  due_date: string;
  status: string;
  item_count: number;
  reserved_item_count: number;
  shortage_item_count: number;
  required_quantity: number;
  reserved_quantity: number;
  shortage_quantity: number;
  created_at: string;
  updated_at: string;
}

export interface InventoryReservation {
  id: number;
  requirement_item_id: number;
  material_id: number;
  warehouse_id: number;
  location_id: number;
  warehouse_name: string;
  location_name: string;
  quantity: number;
  issued_quantity: number;
  status: string;
}

export interface MaterialRequirementItem {
  id: number;
  requirement_id: number;
  component_id?: number | null;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  required_quantity: number;
  unit: string;
  reserved_quantity: number;
  purchased_quantity: number;
  received_quantity: number;
  issued_quantity: number;
  returned_quantity: number;
  shortage_quantity: number;
  status: string;
  reservations: InventoryReservation[];
}

export interface MaterialRequirement extends MaterialRequirementSummary {
  items: MaterialRequirementItem[];
}

export interface PurchaseShortage {
  id: number;
  requirement_item_id: number;
  requirement_id: number;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  demand_quantity: number;
  unit: string;
  due_date: string;
  production_no: string;
  default_supplier: string;
  status: string;
}

export interface PurchaseAllocation {
  id: number;
  requirement_item_id: number;
  allocated_quantity: number;
  received_quantity: number;
  cancelled_quantity: number;
  status: string;
  requirement_no: string;
  production_no: string;
  due_date: string;
}

export interface PurchaseOrderItem {
  id: number;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  ordered_quantity: number;
  received_quantity: number;
  rejected_quantity: number;
  cancelled_quantity: number;
  unit: string;
  unit_price: number;
  status: string;
  allocations: PurchaseAllocation[];
}

export interface PurchaseOrder {
  id: number;
  order_no: string;
  supplier: string;
  expected_date: string;
  status: string;
  total_amount: number;
  remark: string;
  item_count?: number;
  ordered_quantity?: number;
  received_quantity?: number;
  items?: PurchaseOrderItem[];
  created_at: string;
}

export interface PurchaseReceiptItem {
  id: number;
  purchase_order_item_id: number;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  received_quantity: number;
  qualified_quantity: number;
  concession_quantity: number;
  rejected_quantity: number;
  inbound_quantity: number;
  unit: string;
  status: string;
}

export interface PurchaseReceipt {
  id: number;
  receipt_no: string;
  purchase_order_id: number;
  order_no: string;
  supplier: string;
  arrival_date: string;
  status: string;
  remark: string;
  item_count?: number;
  received_quantity?: number;
  items?: PurchaseReceiptItem[];
  created_at: string;
}
