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

const MANAGEMENT_PATH_PREFIXES = [
  "/orders",
  "/cutting",
  "/door-cad/frame",
  "/production",
  "/purchasing",
  "/inventory",
  "/master-data",
  "/payroll",
];

export function canAccessManagement(user: Pick<UserInfo, "uid"> | null | undefined) {
  return user?.uid === "A";
}

export function isManagementPath(pathname: string) {
  return MANAGEMENT_PATH_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
