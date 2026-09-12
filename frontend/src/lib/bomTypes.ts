export type BomWorkbenchState = "待生成" | "待核验" | "缺少资料" | "缺料" | "已发布" | "已变更";

export interface BomWorkbenchSummary {
  total: number;
  pending_generation: number;
  pending_verification: number;
  missing_data: number;
  shortage: number;
  published: number;
  changed: number;
}

export interface BomWorkbenchItem {
  technical_package_id: number;
  version: number;
  status: "草稿" | "已确认";
  generation_status: string;
  rule_version: string;
  generated_at: string | null;
  blocking_warning_count: number;
  updated_at: string;
  door_unit_id: number;
  production_no: string;
  product_name: string;
  specification: string;
  door_status: string;
  due_date: string;
  order_id: number;
  order_no: string;
  sales_order_no: string;
  customer: string;
  project: string;
  item_count: number;
  pending_verification_count: number;
  missing_data_count: number;
  shortage_quantity: number;
  states: BomWorkbenchState[];
}

export interface BomWorkbenchResponse {
  summary: BomWorkbenchSummary;
  items: BomWorkbenchItem[];
  pagination: { page: number; page_size: number; total: number; pages: number };
}

export interface BomRow {
  id: number;
  parent_id: number | null;
  material_id: number | null;
  material_code: string | null;
  material_name: string | null;
  material_specification: string | null;
  material_unit: string | null;
  supplier_id: number | null;
  supplier_name: string | null;
  name: string;
  category: string;
  specification: string;
  quantity: number;
  theoretical_quantity: number;
  waste_rate: number;
  planned_quantity: number;
  unit: string;
  acquisition_method: string;
  group_code: string;
  operation_code: string;
  required_date: string;
  remark: string;
  match_status: string;
  verification_status: string;
  source_type: string;
}

export interface BomGroup {
  code: string;
  label: string;
  count: number;
  rows: BomRow[];
}

export interface BomWarning {
  id: number;
  severity: string;
  field_path: string;
  code: string;
  message: string;
  blocking: number;
}

export interface BomVersion {
  technical_package_id: number;
  version: number;
  status: string;
  generation_status: string;
  rule_version: string;
  blocking_warning_count: number;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
}

export interface BomDetail {
  id: number;
  door_unit_id: number;
  order_id: number;
  order_no: string;
  sales_order_no: string;
  customer: string;
  project: string;
  production_no: string;
  product_name: string;
  specification: string;
  due_date: string;
  version: number;
  status: "草稿" | "已确认";
  generation_status: string;
  rule_version: string;
  generated_at: string | null;
  blocking_warning_count: number;
  product_summary: string;
  special_requirements: string;
  rows: BomRow[];
  groups: BomGroup[];
  warnings: BomWarning[];
  version_history: BomVersion[];
  downstream_impact: { requirement_count: number; supply_count: number; work_package_count: number };
  frame_status: { applicable: boolean; can_calculate: boolean; deferred: boolean; errors: unknown[]; warnings: unknown[] };
}

export interface BomDraftItem {
  id: number;
  material_id: number | null;
  name: string;
  category: string;
  specification: string;
  theoretical_quantity: number;
  waste_rate: number;
  planned_quantity: number;
  quantity: number;
  unit: string;
  acquisition_method: string;
  group_code: string;
  operation_code: string;
  supplier_id: number | null;
  required_date: string;
  remark: string;
}
