# Drawing Entry Save Verification

## Changes
- Entry and drawing editing share DoorForm and DrawingFormActions; button order is preview DXF, generate DXF, generate effect, save form, quote.
- Saving entry retains its content and module, remembers the created task ID, and updates that task thereafter. In-flight saves share one promise.
- Quote and rendering reuse the saved entry ID. Entry quote saves dirty changes first; existing drawing quote retains its existing leave-confirmation workflow.
- Parameters, communication text and reference images share one saved snapshot. Unsaved entry navigation is guarded; clearing resets the entry identity without deleting saved records.
- DXF generation remains a download-only action, and review submission remains separate.

## Checks
- `node --experimental-strip-types --test` for all eight `src/lib/*.test.ts`: 34 passed.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false`: passed.
- Targeted ESLint: no errors, six existing dashboard warnings (unused values, cleanup/dependency notes and image optimization).
- `node tests/quote-dual-trim.cjs`: passed. Tests cover unchanged dual-trim pricing, preview decimals, historical quotes, identical form/action labels, save/stay, repeated save updating one record, failed update retry, reference image/text retention, entry rendering linkage, exact-task quotation, and clearing a saved form without deleting it.
- `node tests/render-quick-only.cjs`: passed; rendering workspace behavior unchanged.
- Desktop 1600x1100 and mobile 390x1000 screenshots inspected. Desktop actions form one row, mobile actions stack without overflow or overlap.
- Browser scenarios mock all API requests. No live records or paid image generation were used. These checks do not validate real model image quality or production deployment.

Artifacts: `F:/codex/dual-trim-quote-verification/entry-actions-desktop.png` and `entry-actions-mobile.png`.
