import assert from "node:assert/strict";
import test from "node:test";
import { filterTrackedInventory } from "./trackedInventory.ts";
import type { TrackedProductionInventoryItem } from "./inventoryTypes.ts";

const items = [
  { warehouse_id: 1, warehouse_type: "半成品", production_no: "TM001", item_name: "门框", customer: "张先生", project: "项目A", door_type: "双开门", specification: "1200x2400" },
  { warehouse_id: 2, warehouse_type: "半成品", production_no: "TM002", item_name: "门扇", customer: "李先生", project: "项目B" },
  { warehouse_id: null, warehouse_type: "半成品", production_no: "TM003", item_name: "门套" },
] as TrackedProductionInventoryItem[];
const defaults = { warehouseId: "", q: "", lowOnly: false };

test("same-type warehouses do not mix", () => {
  assert.deepEqual(filterTrackedInventory(items, { ...defaults, warehouseId: "2" }).map((item) => item.production_no), ["TM002"]);
});

test("unknown warehouse stays visible only in the all-warehouse view", () => {
  assert.equal(filterTrackedInventory(items, defaults).length, 3);
  assert.equal(filterTrackedInventory(items, { ...defaults, warehouseId: "99" }).length, 0);
});

test("search includes production, component, customer, project, door type and dimensions", () => {
  for (const q of ["tm001", "门框", "张先生", "项目A", "双开门", "1200x2400", "张先生 门框"])
    assert.equal(filterTrackedInventory(items, { ...defaults, q }).length, 1, q);
  assert.equal(filterTrackedInventory(items, { ...defaults, q: "不存在" }).length, 0);
});

test("low-stock mode does not misclassify order-specific parts", () => {
  assert.deepEqual(filterTrackedInventory(items, { ...defaults, lowOnly: true }), []);
});

test("all records remain accessible beyond twenty-four rows", () => {
  assert.equal(filterTrackedInventory(Array.from({ length: 30 }, () => items[0]), defaults).length, 30);
});
