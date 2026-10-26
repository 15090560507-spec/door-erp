# Dual Trim Quote Verification

## Delivered

- Outer-area mode with two trims uses the larger actual CAD perimeter rectangle for the main door (outer on ties), retaining that side's width and height together. The other trim is an explicit net-area row, at the main unit price times a configurable factor (default 0.7).
- Uses existing CAD trim contour/net metrics, including existing outer-only lintel ownership. Invalid dual-trim metrics prevent generating an incomplete quote; switching to a failing task does not relabel old rows as the new task.
- Generated-row roles and factor persist in quote JSON and API models. Price changes and row reordering retain the link; editing the extra unit price with a positive main price derives a new factor. Loading history does not silently reprice it.
- Split frame/trim mode and global CAD dimensions are unchanged. Existing main-door minimum area remains; extra trim uses its decimal net area without a main-door minimum.
- Drawing actions: existing task `去报价` uses the existing unsaved-edit guard; new drawing input `保存并报价` validates and saves first. Exact task-ID link opens its latest saved quote, or prefills a new linked quote.
- Preview quantity cells no longer wrap decimal numbers. Measured text fitting keeps unusually long values inside the unchanged A4/table column widths; stored precision is not truncated.

## Checks

- 34 frontend Node tests passed, including six new pricing-helper cases.
- 37 backend quote persistence/model/export, multi-door, contour-geometry and history regressions passed. New cases cover factor/role save and update, old default versus explicit zero, invalid/nonfinite factors, decimal export quantities, exact-task lookup and preserving saved prices.
- TypeScript no-emit check passed. Targeted lint: zero errors and five existing dashboard warnings.
- Mocked Chrome/Playwright `node tests/quote-dual-trim.cjs` passed: outer/inner primary cases, editable factor, linked price after reorder, manually derived factor, 3.7920 and long quantity fitting, save/reload without history repricing, unchanged split mode, unsaved-navigation cancel/save, and new-task save-before-navigation.
- Desktop 1600px and mobile 390px screenshots inspected. No document-level horizontal mobile overflow or page errors; fixed-format quote tables retain their existing inner scrolling behavior.
- Local artifacts: `F:/codex/dual-trim-quote-verification/`. Browser API requests are mocked; no paid providers or production data are used.

No Tencent Cloud deployment was performed.
