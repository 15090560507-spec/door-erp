import assert from "node:assert/strict";
import test from "node:test";
import { calculateDoorAreas } from "./doorAreas.ts";
import { outerQuoteBasis, linkExtraTrimPrices, editOuterQuoteRows } from "./quoteOuterPricing.ts";
import type { QuoteItem, QuoteTrimMetrics } from "./quoteTypes";

const areas = calculateDoorAreas({ dw: 1000, dh: 2000, has_outer: true, has_inner: true, trim_front_in: 150, trim_back_in: 100 } as never);
function metrics(outerWidth = 1300, outerHeight = 2150, innerWidth = 1200, innerHeight = 2100): QuoteTrimMetrics {
  const side = (name: "outer" | "inner", width: number, height: number) => ({ side: name, valid: true, error: "",
    outerBounds: { left: 0, bottom: 0, right: width, top: height, width, height }, innerBounds: null,
    outerArea: width * height / 1e6, innerArea: 2, baseArea: width * height / 1e6 - 2,
    lintelArea: 0, includedLintelArea: 0, quoteArea: width * height / 1e6 - 2 });
  return { source: "cad-trim-contour-v1", lintelTarget: "none", outer: side("outer", outerWidth, outerHeight), inner: side("inner", innerWidth, innerHeight) };
}
test("outer normally determines the door rectangle; inner is charged by net area", () => {
  assert.deepEqual(outerQuoteBasis(areas, metrics()), { width: 1300, height: 2150, side: "outer", extra: { side: "inner", netArea: .52 } });
});
test("larger inner rectangle reverses sides; never mix width and height", () => {
  assert.deepEqual(outerQuoteBasis(areas, metrics(1500, 2100, 1400, 2500)), { width: 1400, height: 2500, side: "inner", extra: { side: "outer", netArea: 1.15 } });
  assert.equal(outerQuoteBasis(areas, metrics(1200, 2200, 1200, 2200)).side, "outer");
});
test("single/no trim uses existing outer specification without extra charge", () => {
  for (const flags of [{ hasFrontOuter: false }, { hasInnerTrim: false }, { hasFrontOuter: false, hasInnerTrim: false }]) {
    assert.equal(outerQuoteBasis({ ...areas, ...flags }, null).extra, null);
  }
});
test("both trim contours must be valid and lintel stays with its existing side", () => {
  assert.throws(() => outerQuoteBasis(areas, null), /轮廓/);
  const value = metrics(1200, 2100, 1400, 2300);
  value.outer.quoteArea += .123456;
  assert.equal(outerQuoteBasis(areas, value).extra?.netArea, .6435);
  value.inner.valid = false;
  assert.throws(() => outerQuoteBasis(areas, value), /轮廓/);
});
const rows = [{ pricingRole: "mainDoor", unitPrice: 1480 }, { pricingRole: "extraTrim", unitPrice: 1036 }, { unitPrice: 80 }] as QuoteItem[];
test("unit price links by role rather than row order, with editable factor and zero", () => {
  assert.equal(linkExtraTrimPrices([...rows].reverse(), .8).find(row => row.pricingRole === "extraTrim")?.unitPrice, 1184);
  assert.equal(linkExtraTrimPrices(rows, 0)[1].unitPrice, 0);
  assert.equal(linkExtraTrimPrices(rows, .7)[2].unitPrice, 80);
});
test("manual extra price updates factor; main-price edits preserve the factor", () => {
  const manual = editOuterQuoteRows(rows, rows.map(row => row.pricingRole === "extraTrim" ? { ...row, unitPrice: 1184 } : row), .7);
  assert.equal(manual.factor, .8);
  const changed = editOuterQuoteRows(rows, rows.map(row => row.pricingRole === "mainDoor" ? { ...row, unitPrice: 2000 } : row), .7);
  assert.equal(changed.items[1].unitPrice, 1400);
  assert.equal(changed.factor, .7);
});
