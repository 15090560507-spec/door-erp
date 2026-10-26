import assert from "node:assert/strict";
import test from "node:test";

import { GLASS_LINE_STYLE_LABELS, panelGlassControlScope } from "./glassPatternControls.ts";

test("bars expose pitch, without glass inset", () => {
  assert.deepEqual(panelGlassControlScope("H型布局", "竖条", "六格线条"), {
    insetRegions: "", spacingRegions: "B2", spacingIsBarsOnly: true,
  });
});

test("all patterns with internal lines expose spacing", () => {
  for (const pattern of ["竖条", "四角回纹", "双边框", "双边框+花件", "六格线条", "八格线条"]) {
    assert.equal(panelGlassControlScope("H型布局", pattern, "无线条").spacingRegions, "B2", pattern);
  }
});

test("perimeters expose only inset and no-lines exposes neither", () => {
  for (const pattern of ["单圈外围线", "单圈外围线(封闭)"]) {
    assert.deepEqual(panelGlassControlScope("H型布局", pattern, "无线条"), {
      insetRegions: "B2", spacingRegions: "", spacingIsBarsOnly: false,
    });
  }
  for (const style of ["无造型", "大板布局", "H型布局"]) {
    assert.deepEqual(panelGlassControlScope(style, "无线条", "八格线条"), {
      insetRegions: "", spacingRegions: "", spacingIsBarsOnly: false,
    });
  }
});

test("mixed H+ regions identify which input affects each region", () => {
  assert.deepEqual(panelGlassControlScope("H+型布局", "竖条", "单圈外围线"), {
    insetRegions: "B4", spacingRegions: "B2", spacingIsBarsOnly: true,
  });
  assert.deepEqual(panelGlassControlScope("H+型布局", "六格线条", "八格线条"), {
    insetRegions: "B2/B4", spacingRegions: "B2/B4", spacingIsBarsOnly: false,
  });
});

test("display label adds glass without changing the persisted option", () => {
  assert.equal(GLASS_LINE_STYLE_LABELS["单圈外围线"], "单圈外围线（玻璃）");
  assert.equal(GLASS_LINE_STYLE_LABELS["单圈外围线(封闭)"], undefined);
});
