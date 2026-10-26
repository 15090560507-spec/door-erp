import assert from "node:assert/strict";
import test from "node:test";
import { clampFloatingPosition, clampFloatingSize, DEFAULT_FLOATING_SIZE, initialFloatingPosition, shouldDockPreview } from "./floatingPreview.ts";

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
  assert.deepEqual(initialFloatingPosition({ width: 1920, height: 1080 }), { x: 1394, y: 96 });
  assert.deepEqual(initialFloatingPosition({ width: 300, height: 260 }), { x: 8, y: 8 });
});

test("default window is 1.5x wider and resize dimensions remain bounded", () => {
  assert.equal(DEFAULT_FLOATING_SIZE.width, 340 * 1.5);
  assert.equal(DEFAULT_FLOATING_SIZE.height, 440 * 1.5);
  assert.deepEqual(clampFloatingSize({ width: 9000, height: 9000 }, { width: 390, height: 700 }), { width: 374, height: 684 });
  assert.deepEqual(clampFloatingSize({ width: 20, height: 20 }, { width: 1920, height: 1080 }), { width: 280, height: 240 });
});

test("docking begins when the save bar reaches the lower preview region", () => {
  assert.equal(shouldDockPreview(1100, 1000), false);
  assert.equal(shouldDockPreview(1000, 1000), true);
  assert.equal(shouldDockPreview(-10, 1000), true);
  assert.equal(shouldDockPreview(1100, 1000), false);
});
