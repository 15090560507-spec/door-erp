import type { ModuleName, UserInfo } from "@/lib/types";

export const MANAGEMENT_MODULES: ModuleName[] = [
  "订单确认",
  "下料",
  "生产管理",
  "采购管理",
  "库存管理",
  "基础资料",
  "工资管理",
];

const MODULE_PERMISSIONS: Partial<Record<ModuleName, string[]>> = {
  "订单确认": ["sales.read", "finance.read"],
  "下料": ["production.technical", "production.cutting"],
  "生产管理": ["production.read"],
  "采购管理": ["inventory.read"],
  "库存管理": ["inventory.read"],
  "基础资料": ["masterdata.read", "personnel.write"],
  "工资管理": ["payroll.read", "attendance.write"],
};
const PATH_MODULES: Record<string, ModuleName> = {
  "/orders": "订单确认", "/cutting": "下料", "/door-cad/frame": "下料",
  "/production": "生产管理", "/purchasing": "采购管理", "/inventory": "库存管理",
  "/master-data": "基础资料", "/payroll": "工资管理",
};
type BusinessUser = Pick<UserInfo, "uid"> & Partial<Pick<UserInfo, "role" | "permissions">>;

export function isBusinessAdmin(user: BusinessUser | null | undefined) {
  return user?.uid === "A" || user?.role === "超级管理员";
}

export function hasBusinessPermission(user: BusinessUser | null | undefined, permission: string) {
  return isBusinessAdmin(user) || Boolean(user?.permissions?.includes(permission));
}

export function canAccessManagement(user: BusinessUser | null | undefined, module?: ModuleName) {
  const permissions = module ? MODULE_PERMISSIONS[module] || [] : Object.values(MODULE_PERMISSIONS).flat();
  return isBusinessAdmin(user) || permissions.some((permission) => hasBusinessPermission(user, permission));
}

export function isManagementPath(pathname: string) {
  return Object.keys(PATH_MODULES).some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function canAccessManagementPath(user: BusinessUser | null | undefined, pathname: string) {
  const prefix = Object.keys(PATH_MODULES).find((path) => pathname === path || pathname.startsWith(`${path}/`));
  return !prefix || canAccessManagement(user, PATH_MODULES[prefix]);
}
