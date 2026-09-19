import assert from "node:assert/strict";
import test from "node:test";

import {
  QUOTE_PREVIEW_COLUMN_WIDTHS_MM,
  QUOTE_PREVIEW_PAGE_WIDTH_MM,
  QUOTE_PREVIEW_PADDING_MM,
  QUOTE_PREVIEW_ROW_HEIGHTS_MM,
  QUOTE_PREVIEW_TABLE_WIDTH_MM,
  millimeters,
} from "./quotePreviewLayout.ts";

test("preview columns retain the exported JPG layout width", () => {
  assert.equal(QUOTE_PREVIEW_COLUMN_WIDTHS_MM.length, 10);
  assert.ok(Math.abs(QUOTE_PREVIEW_TABLE_WIDTH_MM - 206.8) < 0.000001);
  assert.ok(
    QUOTE_PREVIEW_TABLE_WIDTH_MM <= QUOTE_PREVIEW_PAGE_WIDTH_MM,
    "table must fit inside the A4 preview width",
  );
  assert.ok(
    QUOTE_PREVIEW_TABLE_WIDTH_MM >= QUOTE_PREVIEW_PAGE_WIDTH_MM - QUOTE_PREVIEW_PADDING_MM * 2,
    "table should use the same near-full-page width as the exported JPG",
  );
});

test("long-text sections retain the exported JPG minimum heights", () => {
  assert.equal(QUOTE_PREVIEW_ROW_HEIGHTS_MM.intro, 22.6);
  assert.equal(QUOTE_PREVIEW_ROW_HEIGHTS_MM.terms, 23.4);
  assert.equal(QUOTE_PREVIEW_ROW_HEIGHTS_MM.invoice, 37);
  assert.equal(QUOTE_PREVIEW_ROW_HEIGHTS_MM.bank, 28.6);
  assert.equal(millimeters(37), "37mm");
});
