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
  brand: string;
  purchase_unit: string;
  purchase_conversion: number;
  standard_sale_price: number;
  reference_purchase_price: number;
  safety_stock: number;
  can_sell: number;
  can_purchase: number;
  manage_stock: number;
  can_subcontract: number;
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
  brand?: string;
  purchase_unit?: string;
  purchase_conversion?: number;
  standard_sale_price?: number;
  reference_purchase_price?: number;
  safety_stock?: number;
  can_sell?: boolean;
  can_purchase?: boolean;
  manage_stock?: boolean;
  can_subcontract?: boolean;
  remark: string;
  is_active?: boolean;
}

export interface InventorySupplier {
  id: number;
  code: string;
  name: string;
  short_name: string;
  contact_name: string;
  phone: string;
  address: string;
  invoice_title: string;
  tax_no: string;
  default_tax_rate: number;
  settlement_method: string;
  payment_days: number;
  default_lead_days: number;
  supply_category: string;
  is_active: number;
  remark: string;
  item_count: number;
}

export type SupplierPayload = Omit<InventorySupplier, "id" | "item_count" | "is_active"> & { is_active?: boolean };

export interface InventorySupplierItem {
  id: number;
  supplier_id: number;
  material_id: number;
  supplier_code: string;
  supplier_name: string;
  material_code: string;
  material_name: string;
  material_specification: string;
  supplier_item_code: string;
  supplier_item_name: string;
  purchase_specification: string;
  purchase_unit: string;
  conversion_rate: number;
  tax_inclusive_price: number;
  tax_rate: number;
  minimum_order_quantity: number;
  lead_days: number;
  is_preferred: number;
  is_active: number;
  remark: string;
}

export interface SupplierItemPayload {
  supplier_id: number;
  material_id: number;
  supplier_item_code: string;
  supplier_item_name: string;
  purchase_specification: string;
  purchase_unit: string;
  conversion_rate: number;
  tax_inclusive_price: number;
  tax_rate: number;
  minimum_order_quantity: number;
  lead_days: number;
  is_preferred: boolean;
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

export interface PendingMaterialIssue {
  reservation_id: number;
  requirement_item_id: number;
  requirement_id: number;
  order_id: number;
  door_unit_id: number;
  production_no: string;
  due_date: string;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  unit: string;
  warehouse_id: number;
  location_id: number;
  warehouse_name: string;
  location_name: string;
  available_quantity: number;
}

export interface MaterialFlowItem {
  id: number;
  requirement_item_id?: number | null;
  reservation_id?: number | null;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  source_warehouse_id?: number | null;
  source_location_id?: number | null;
  target_warehouse_id?: number | null;
  target_location_id?: number | null;
  source_warehouse_name?: string;
  source_location_name?: string;
  target_warehouse_name?: string;
  target_location_name?: string;
  quantity: number;
  unit: string;
  remark: string;
}

export interface MaterialFlowOrder {
  id: number;
  document_no: string;
  document_type: string;
  requirement_id?: number | null;
  production_no: string;
  status: string;
  remark: string;
  item_count?: number;
  total_quantity?: number;
  items?: MaterialFlowItem[];
  created_at: string;
}

export interface SubcontractItem {
  id: number;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  source_warehouse_id: number;
  source_location_id: number;
  transit_warehouse_id: number;
  transit_location_id: number;
  sent_quantity: number;
  returned_quantity: number;
  accepted_quantity: number;
  rejected_quantity: number;
  unit: string;
  production_no: string;
  status: string;
}

export interface SubcontractOrder {
  id: number;
  subcontract_no: string;
  supplier: string;
  work_package: string;
  expected_return_date: string;
  status: string;
  remark: string;
  item_count?: number;
  sent_quantity?: number;
  returned_quantity?: number;
  pending_quantity?: number;
  items?: SubcontractItem[];
  created_at: string;
}

export interface SubcontractReceiptItem {
  id: number;
  subcontract_item_id: number;
  material_id: number;
  material_code: string;
  material_name: string;
  specification: string;
  production_no: string;
  returned_quantity: number;
  accepted_quantity: number;
  rejected_quantity: number;
  unit: string;
  status: string;
}

export interface SubcontractReceipt {
  id: number;
  receipt_no: string;
  subcontract_order_id: number;
  subcontract_no: string;
  supplier: string;
  return_date: string;
  status: string;
  item_count?: number;
  items?: SubcontractReceiptItem[];
}
