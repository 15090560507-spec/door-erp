# Quote Door Quantity Verification

Date: 2026-10-18

## Scope

- Same-specification groups carry a positive integer `doorQuantity`, legacy default 1.
- Quote rows remain per-door. Rounded per-door item amounts are summed, then multiplied once by the group count.
- Save/reload, history counts, browser preview, Excel, shared HTML/JPG/PDF and new order handoff use the count.
- Order quote choices retain per-door prices. New quote snapshots preserve per-door rounding when extended; historical snapshots retain their existing rule and stored totals are not rewritten.
- Linked drawing labels append calculated outer dimensions when trim or portal additions change the envelope. No geometry or area rules changed.

## Checks

- Backend: 46 passed, 16 subtests passed across quantity, quote history, multi-door, sales orders, fulfillment bridge and receipt suites.
- TypeScript: `npx tsc --noEmit` passed.
- ESLint: all changed frontend files passed scoped lint.
- Pure TypeScript contracts: `node tools/test_quote_quantities.mjs` passed quantity, legacy, outer-dimension and order-rounding cases.
- Playwright: `node tools/verify_quote_door_quantity.mjs` passed at 1440px and 390px, covering count controls, preview totals, invalid-count save prevention, save/reload, full linked dimensions, order handoff, quantity edits and quote switching.
- Actual shared renderer produced HTML, JPG and PDF. The sample is 11,615 per door x 2 doors = 23,230, with one lock per door. JPG reviewed visually; the per-door quantity header uses two lines to avoid clipping.
- Actual Excel sample generated; tests verify subtotal multiplication occurs once and per-door accessory quantity remains 1.

## Isolation

Backend tests use an isolated DATA_DIR and temporary repositories. Browser tests intercept API calls with fixtures and perform no real business-data writes or paid AI calls. Confirmed orders, account data and CAD generation are outside this change.

Local verification artifacts: `F:/codex/quote-door-quantity-verification`.
