import assert from "node:assert/strict";
import test from "node:test";
import type { SalesOrderLine } from "./salesOrderTypes.ts";
import { orderLineOverview, orderLineValue } from "./salesOrderDisplay.ts";

const line = () => ({ product_name: "确认门", door_type: "对开门", width: 1600, height: 2370,
  opening_direction: "右内开", color: "确认色", technical_details: { main_door_style: "订单确认款式" },
  drawing_snapshot: { params: { product_name: "历史门", dw: 900, dh: 2100, zmks: "快照款式", fmks: "反面雕花", frame_process: "折弯工艺", glass_spec: "超白玻璃" } },
} as unknown as SalesOrderLine);

test("confirmed technical fields override line and frozen snapshot fallbacks", () => {
  const row = line();
  row.main_door_style = "行款式";
  assert.equal(orderLineValue(row, ["main_door_style", "zmks"]), "订单确认款式");
  row.technical_details.main_door_style = "";
  assert.equal(orderLineValue(row, ["main_door_style", "zmks"]), "行款式");
  row.main_door_style = "";
  assert.equal(orderLineValue(row, ["main_door_style", "zmks"]), "快照款式");
});
test("overview does not replace confirmed dimensions with snapshot dimensions", () => {
  assert.deepEqual(orderLineOverview(line()), { product: "确认门", doorType: "对开门", dimensions: "1600 × 2370 mm", opening: "右内开", color: "确认色" });
});
test("historical orders without technical details still display snapshot facts without mutation", () => {
  const row = { ...line(), technical_details: undefined, product_name: "", door_type: "", width: 0, height: 0,
    opening_direction: "", color: "", drawing_snapshot: { params: { dw: 900, dh: 2100, product_name: "历史门", door_type: "单门", sel_kx: "左开", sel_nk: "外开", ys: "古铜色", fmks: "反面雕花" } } } as unknown as SalesOrderLine;
  const original = JSON.stringify(row);
  assert.equal(orderLineValue(row, ["fmks"]), "反面雕花");
  assert.deepEqual(orderLineOverview(row), { product: "历史门", doorType: "单门", dimensions: "900 × 2100 mm", opening: "左开外开", color: "古铜色" });
  assert.equal(JSON.stringify(row), original);
  assert.equal(orderLineValue({} as SalesOrderLine, ["glass_spec"]), undefined);
});
