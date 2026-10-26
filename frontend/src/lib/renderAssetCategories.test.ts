import assert from "node:assert/strict";
import test from "node:test";
import { RENDER_CATEGORIES, renderCategoryLabel, renderCategoryRole } from "./renderAssetCategories.ts";
import { clipboardImageFiles, isClipboardTextTarget } from "./clipboardImages.ts";

test("reference categories have the exact approved labels and order", () => {
  assert.deepEqual(RENDER_CATEGORIES, ["门扇款式", "拉手", "合页", "颜色", "门套款式", "花件"]);
});

test("category roles are automatic, with an explicit color target", () => {
  assert.deepEqual(RENDER_CATEGORIES.map(value => renderCategoryRole(value)), ["panel", "hardware", "hardware", "panel", "trim", "hardware"]);
  assert.equal(renderCategoryRole("颜色", "trim"), "trim");
  assert.equal(renderCategoryRole("拉手", "panel"), "hardware");
});

test("historical categories keep compatible labels and roles", () => {
  assert.equal(renderCategoryLabel("包套"), "门套款式");
  assert.equal(renderCategoryLabel("门扇"), "门扇款式");
  assert.equal(renderCategoryRole("门头"), "trim");
  assert.equal(renderCategoryRole("纹理", "frame"), "frame");
  assert.equal(renderCategoryRole("玻璃"), "glass");
});

test("clipboard images are not duplicated between files and items", () => {
  const file = new File(["image"], "screen.png", { type: "image/png" });
  const data = { files: [file], items: [{ kind: "file", type: file.type, getAsFile: () => file }] };
  assert.deepEqual(clipboardImageFiles(data as unknown as DataTransfer), [file]);
  assert.deepEqual(clipboardImageFiles({ ...data, files: [] } as unknown as DataTransfer), [file]);
});

test("text and unrelated clipboard files do not become uploads", () => {
  const file = new File(["hello"], "text.txt", { type: "text/plain" });
  assert.deepEqual(clipboardImageFiles({ files: [file], items: [] } as unknown as DataTransfer), []);
  assert.equal(isClipboardTextTarget(null), false);
  assert.equal(isClipboardTextTarget({ closest: () => ({}) } as unknown as EventTarget), true);
  assert.equal(isClipboardTextTarget({ closest: () => null } as unknown as EventTarget), false);
});
