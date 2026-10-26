import assert from "node:assert/strict";
import test from "node:test";
import { panCadView, zoomCadView } from "./cadViewport.ts";

const box = { x: 10, y: 20, width: 1000, height: 2000 };
test("pan moves the drawing with the pointer without resizing", () => {
  assert.deepEqual(panCadView(box, 100, -200), { x: -90, y: 220, width: 1000, height: 2000 });
});
test("right drag zoom is uniform and keeps the pointed drawing coordinate anchored", () => {
  const anchor = { x: 260, y: 1020 };
  const zoomed = zoomCadView(box, box, anchor, -100);
  assert.ok(zoomed.width < box.width);
  assert.equal(zoomed.height / zoomed.width, 2);
  assert.ok(Math.abs((anchor.x - zoomed.x) / zoomed.width - 0.25) < 1e-9);
  assert.ok(Math.abs((anchor.y - zoomed.y) / zoomed.height - 0.5) < 1e-9);
  assert.ok(zoomCadView(box, box, anchor, 100).width > box.width);
});
test("zoom cannot collapse or explode the viewBox", () => {
  assert.equal(zoomCadView(box, box, { x: 0, y: 0 }, -100000).width, 125);
  assert.equal(zoomCadView(box, box, { x: 0, y: 0 }, 100000).width, 8000);
});
