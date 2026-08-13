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
