# Compact Form and Optional Live Preview Verification

## Delivered Behavior
- Quote image recognition follows the quote preview and is never invoked automatically.
- Both drawing entry and editing use the same rebalanced three-column form: order/material/hardware; structure/dimensions/frame; expanded panel settings/trim/notes. Gap settings remain collapsible. Parameter data and pricing are unchanged.
- The right-side dock is sticky at viewport widths of at least 1700px; narrower screens place it below the form without covering fields. Trim grids adapt to available width; short structural checkbox labels wrap as whole options.
- Automatic preview is off by default and resets across tasks/newly cleared forms. Manual refresh remains available. Auto mode waits 1500ms after geometry edits; customer/order/date/notes/quantity metadata do not trigger CAD generation.
- The queue allows one request at a time and replaces intermediate pending jobs with the newest snapshot. Stale results cannot replace the current drawing. Disable cancels pending work; leaving disposes the queue and ignores in-flight completions.
- Last successful drawing remains during updates and failures. Cache is limited to eight SVGs and four million characters; larger SVGs can be shown without retention. A changed-parameters status distinguishes an old preview from current input.
- Preview only requires geometry-related backend-required fields, not a fully completed commercial form. Incomplete geometry is reported inline, without validation popups. Preview never saves records or calls AI.

## Checks
- Frontend library tests: 41 passed, including six latest-preview queue/readiness/cache tests.
- TypeScript noEmit passed. Targeted ESLint: no errors; eight pre-existing warnings in dashboard and DoorForm.
- Extended `quote-dual-trim.cjs` passed with real generated CAD SVG fixture and mocked APIs: relocation order, three-column grouping, expanded panel, right sticky placement, opt-in default, debounce, metadata suppression, off switch, serialized delayed updates/stale suppression, failed refresh retaining previous SVG, manual retry, no auto-save and cross-task reset.
- Existing save/quote/history/area/preview navigation scenarios also passed. Rendering workspace regression `render-quick-only.cjs` passed.
- Desktop 1920x1100 and mobile 390x1000 screenshots inspected; no document overflow or obstructed controls. Artifacts: `F:/codex/compact-form-verification/three-column-desktop.png` and `live-preview-mobile.png`.
- All browser model/API calls were mocked. No production records, paid model calls or server deployment were involved. CAD computation load remains real when the user enables auto mode in production; debounce and serialization reduce, but do not eliminate, that cost.
