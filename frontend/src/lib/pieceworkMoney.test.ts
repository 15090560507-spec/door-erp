import assert from "node:assert/strict";
import test from "node:test";
import { formatPieceworkCents, parsePieceworkCents } from "./pieceworkMoney.ts";

test("manual allocations sum in cents, not binary fractional amounts", () => {
  assert.equal(parsePieceworkCents("0.10")! + parsePieceworkCents("0.20")!, 30);
  assert.equal(formatPieceworkCents(30), "0.30");
  assert.equal(formatPieceworkCents(8800), "88.00");
});

test("rejects invalid allocation amounts without rounding", () => {
  for (const value of ["", "-1", "NaN", "Infinity", "0.001", "1e2", "90000000000001"]) {
    assert.equal(parsePieceworkCents(value), null);
  }
});
