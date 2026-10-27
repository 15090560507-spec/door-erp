import assert from "node:assert/strict";
import test from "node:test";
import { canAccessManagement, canAccessManagementPath, hasBusinessPermission, isBusinessAdmin } from "./managementAccess.ts";

test("A and superadmin retain all business access without changing their roles", () => {
  for (const user of [{ uid: "A", role: "录入员", permissions: [] }, { uid: "root", role: "超级管理员", permissions: [] }]) {
    assert.equal(isBusinessAdmin(user), true);
    assert.equal(hasBusinessPermission(user, "finance.release"), true);
    assert.equal(canAccessManagementPath(user, "/payroll"), true);
  }
});
test("ordinary users only see their authorized modules", () => {
  const user = { uid: "E", role: "录入员", permissions: ["sales.read", "production.read"] };
  assert.equal(canAccessManagement(user, "订单确认"), true);
  assert.equal(canAccessManagement(user, "生产管理"), true);
  assert.equal(canAccessManagement(user, "工资管理"), false);
  assert.equal(canAccessManagementPath(user, "/payroll"), false);
  assert.equal(canAccessManagementPath(user, "/door-cad/frame/42"), false);
  assert.equal(hasBusinessPermission(user, "finance.release"), false);
  assert.equal(canAccessManagement(null), false);
});
test("separate grants do not confer approval or unlock privilege", () => {
  const user = { uid: "F", permissions: ["payroll.read", "payroll.write"] };
  assert.equal(canAccessManagement(user, "工资管理"), true);
  assert.equal(hasBusinessPermission(user, "payroll.approve"), false);
  assert.equal(hasBusinessPermission(user, "payroll.unlock"), false);
});
