import assert from "node:assert/strict";
import test from "node:test";
import { clampFloatingPosition, initialFloatingPosition } from "./floatingPreview.ts";

test("free movement within the viewport is retained", () => {
  assert.deepEqual(clampFloatingPosition({ x: 230, y: 150 }, { width: 340, height: 400 }, { width: 1920, height: 1080 }), { x: 230, y: 150 });
});
test("dragging beyond any screen edge stays reachable", () => {
  const panel = { width: 340, height: 400 }, viewport = { width: 1000, height: 800 };
  assert.deepEqual(clampFloatingPosition({ x: -1000, y: -1000 }, panel, viewport), { x: 8, y: 8 });
  assert.deepEqual(clampFloatingPosition({ x: 10000, y: 10000 }, panel, viewport), { x: 652, y: 392 });
});
test("resize and larger preview content re-clamp the position", () => {
  assert.deepEqual(clampFloatingPosition({ x: 1300, y: 800 }, { width: 340, height: 600 }, { width: 390, height: 700 }), { x: 42, y: 92 });
});
test("initial position fits desktop and narrow screens", () => {
  assert.deepEqual(initialFloatingPosition({ width: 1920, height: 1080 }), { x: 1564, y: 96 });
  assert.deepEqual(initialFloatingPosition({ width: 300, height: 260 }), { x: 8, y: 8 });
});
