import assert from "node:assert/strict";
import test from "node:test";

import { calculateDoorAreas } from "./doorAreas.ts";

const base = {
  dw: 1000,
  dh: 2000,
  use_light_size: false,
  sel_qc: "无",
  qc_height: 0,
  has_mm: true,
  mm_height: 200,
  has_outer: false,
  has_outer_portal: false,
  has_outer_portal2: false,
  has_outer_landscape: false,
  trim_front_in: 100,
  overlap_front: 20,
  overlap_front_lr: 20,
  overlap_front_top: 20,
  has_inner: false,
  trim_back_in: 80,
  overlap_back: 10,
  overlap_back_lr: 10,
  overlap_back_top: 10,
};

function closeTo(actual: number, expected: number) {
  assert.ok(Math.abs(actual - expected) < 0.000001, `${actual} != ${expected}`);
}

test("lintel belongs to outer trim when outer trim exists", () => {
  const areas = calculateDoorAreas({ ...base, has_outer: true } as never);
  closeTo(areas.lintelArea, 0.192);
  closeTo(areas.frontTrimArea, 0.6048);
  closeTo(areas.backTrimArea, 0);
});

test("lintel belongs to inner trim when only inner trim exists", () => {
  const areas = calculateDoorAreas({ ...base, has_inner: true } as never);
  closeTo(areas.lintelArea, 0.196);
  closeTo(areas.frontTrimArea, 0);
  closeTo(areas.backTrimArea, 0.5558);
});

test("lintel is not charged twice when both trims exist", () => {
  const areas = calculateDoorAreas({ ...base, has_outer: true, has_inner: true } as never);
  closeTo(areas.lintelArea, 0.192);
  closeTo(areas.frontTrimArea, 0.6048);
  closeTo(areas.backTrimArea, 0.3598);
});

test("lintel is not charged without trim", () => {
  const areas = calculateDoorAreas(base as never);
  closeTo(areas.lintelArea, 0);
  closeTo(areas.frontTrimArea, 0);
  closeTo(areas.backTrimArea, 0);
});
