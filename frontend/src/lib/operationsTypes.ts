export interface WorkforceEmployee {
  id: number;
  employee_no: string;
  name: string;
  team: string;
  role_name: string;
  capabilities: string[];
  work_center: string;
  wage_type: string;
  base_salary: number;
  hire_date: string;
  leave_date: string;
  is_active: boolean;
  remark: string;
}

export interface PersonnelCurrentWork {
  work_package_id: number;
  door_unit_id: number;
  order_id: number;
  production_no: string;
  operation_name: string;
  status: string;
}

export interface PersonnelWorkEmployee {
  id: number;
  employee_no: string;
  name: string;
  role_name: string;
  status: "工作中" | "待开工" | "待检" | "暂停" | "异常" | "返工" | "空闲";
  current_work: PersonnelCurrentWork | null;
}

export interface PersonnelWorkDepartment {
  name: string;
  employees: PersonnelWorkEmployee[];
}

export interface RouteStep {
  id?: number;
  step_code: string;
  name: string;
  category: string;
  sequence_no: number;
  predecessor_codes: string[];
  material_operations: string[];
  applicable_groups: string[];
  inspection_required: boolean;
  standard_minutes: number;
  piece_rate: number | string;
  default_role: string;
  work_center: string;
  weight: number;
  is_active: boolean;
}

export interface RouteTemplate {
  id: number;
  code: string;
  name: string;
  target_group: string;
  version: number;
  is_default: boolean;
  is_active: boolean;
  steps: RouteStep[];
}

export interface AttendanceRow {
  id: number;
  employee_id: number;
  employee_no: string;
  name: string;
  work_date: string;
  regular_hours: number;
  overtime_hours: number;
  leave_hours: number;
  remark: string;
}

export interface PayrollEntry {
  id: number;
  employee_id: number;
  employee_no: string;
  name: string;
  team: string;
  wage_type: string;
  base_salary: number;
  piecework_amount: number;
  overtime_amount: number;
  allowance: number;
  bonus: number;
  deduction: number;
  social_insurance: number;
  tax: number;
  other_withholding: number;
  payable_amount: number;
  remark: string;
}

export interface PayrollPeriod {
  id: number;
  month: string;
  status: "草稿" | "待审核" | "已审批" | "已锁定";
  approved_by?: string;
  approved_at?: string;
  entries?: PayrollEntry[];
}

export interface PieceworkAllocation {
  employee_id: number;
  amount_cents: number;
  note: string;
  employee_name: string;
  employee_no: string;
}

export interface DoorOperationFee {
  id: number;
  door_unit_id: number;
  technical_package_id: number;
  billing_operation_code: string;
  name: string;
  status: "加工中" | "需核对" | "待分配" | "未设置计件单价" | "已确认";
  revision: number;
  total_cents: number;
  allocated_cents: number;
  remaining_cents: number;
  completed_at: string | null;
  allocations: PieceworkAllocation[];
}

export interface PieceworkAllocationSave {
  revision: number;
  confirm: boolean;
  allocations: Array<{ employee_id: number; amount: string; note: string }>;
}
