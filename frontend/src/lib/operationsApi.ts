import { api } from "./api";
import type { AttendanceRow, PayrollEntry, PayrollPeriod, PersonnelWorkDepartment, RouteTemplate, WorkforceEmployee } from "./operationsTypes";

export type EmployeePayload = Omit<WorkforceEmployee, "id">;

export async function getEmployees() {
  const { data } = await api.get<{ employees: WorkforceEmployee[] }>("/operations/employees");
  return data.employees;
}

export async function getPersonnelWork() {
  const { data } = await api.get<{ departments: PersonnelWorkDepartment[] }>("/operations/personnel-work");
  return data.departments;
}

export async function createEmployee(payload: EmployeePayload) {
  const { data } = await api.post<{ employee: WorkforceEmployee; message: string }>("/operations/employees", payload);
  return data;
}

export async function updateEmployee(id: number, payload: EmployeePayload) {
  const { data } = await api.put<{ employee: WorkforceEmployee; message: string }>(`/operations/employees/${id}`, payload);
  return data;
}

export async function deactivateEmployee(id: number) {
  const { data } = await api.delete<{ message: string }>(`/operations/employees/${id}`);
  return data;
}

export async function getRouteTemplates() {
  const { data } = await api.get<{ templates: RouteTemplate[] }>("/operations/route-templates");
  return data.templates;
}

export async function updateRouteTemplate(template: RouteTemplate) {
  const { data } = await api.put<{ template: RouteTemplate; message: string }>(`/operations/route-templates/${template.id}`, template);
  return data;
}

export async function saveAssemblyAssignment(doorId: number, payload: { owner_id: number | null; collaborator_ids: number[]; work_center: string; planned_date: string; actual_date: string; note: string }) {
  const { data } = await api.put(`/operations/door-units/${doorId}/assembly-assignment`, payload);
  return data;
}

export async function getAttendance(month: string) {
  const { data } = await api.get<{ attendance: AttendanceRow[] }>("/operations/attendance", { params: { month } });
  return data.attendance;
}

export async function saveAttendance(payload: { employee_id: number; work_date: string; regular_hours: number; overtime_hours: number; leave_hours: number; remark: string }) {
  const { data } = await api.post<{ message: string }>("/operations/attendance", payload);
  return data;
}

export async function getPayrollPeriods() {
  const { data } = await api.get<{ periods: PayrollPeriod[] }>("/operations/payroll");
  return data.periods;
}

export async function getPayrollPeriod(id: number) {
  const { data } = await api.get<{ period: PayrollPeriod }>(`/operations/payroll/${id}`);
  return data.period;
}

export async function calculatePayroll(month: string) {
  const { data } = await api.post<{ period: PayrollPeriod; message: string }>("/operations/payroll/calculate", { month });
  return data;
}

export async function updatePayrollEntry(id: number, payload: Pick<PayrollEntry, "overtime_amount" | "allowance" | "bonus" | "deduction" | "social_insurance" | "tax" | "other_withholding" | "remark">) {
  const { data } = await api.put<{ period: PayrollPeriod; message: string }>(`/operations/payroll/entries/${id}`, payload);
  return data;
}

export async function updatePayrollStatus(id: number, status: PayrollPeriod["status"]) {
  const { data } = await api.put<{ period: PayrollPeriod; message: string }>(`/operations/payroll/${id}/status`, { status });
  return data;
}
