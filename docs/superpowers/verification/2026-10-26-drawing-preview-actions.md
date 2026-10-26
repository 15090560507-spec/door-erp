# Drawing Preview and Quote Action Verification

## Scope
- The drawing preview is absent before clicking Preview DXF. Each generation defaults to both views. Its toolbar contains front/back/both and fullscreen, with no second generate button.
- The existing cached preview endpoint accepts `doors_only=true`. It returns front/back SVG groups, excludes ORDER_FORM content and remote notes, and retains nearby dimensions. Legacy callers still receive the old SVG format using a separate cache entry.
- The browser fits actual rendered group bounds with a 2% margin and uniform scaling. Side switching is local, does not regenerate DXF, and preserves the shared coordinate system. The inline canvas ratio adapts to the selected content; fullscreen is portaled above navigation and supports Escape.
- Drawing actions are preview DXF, generate DXF, generate effect, quote, save. The first four share one style; only save is highlighted.
- Dirty/new forms require explicit save-and-quote confirmation. Cancel retains the form; success opens its exact saved task. Task-list quotation appears before copy/delete and does not trigger editing or create a new record.
- No DXF download geometry, order-sheet printing, review workflow or pricing formulas were changed.

## Verification
- Frontend library unit tests: 35 passed.
- Backend unittest selection: 54 passed (`test_cad_download`, `test_cad_preview_views`, and five quote/trim suites). Includes query parsing, legacy/grouped cache isolation, fallback for simple products and real generated single/double/two-fixed-two-opening door SVGs. The logged conversion exception is an intentional negative-path test.
- TypeScript noEmit: passed. Targeted ESLint: no errors, six pre-existing dashboard warnings.
- Browser quote/form regression passed with each of the three real generated SVG fixtures; no uncaught errors or unexpected API calls. Additional final run verifies regeneration resets selection to both views.
- Browser checks include default-hidden preview, no duplicate generation button, no API request on side switching, full bounding-box visibility, uniform SVG transforms, unchanged pricing/history, save confirmation/cancel, row quote routing, and duplicate-save protection.
- Desktop 1600x1100 and mobile 390x1000 screenshots inspected. The mobile inline canvas has no large unused vertical region, document overflow or overlapping buttons. The wide four-panel drawing also fits.
- Rendering workspace regression `render-quick-only.cjs`: passed.
- Browser APIs/model generation were mocked; no paid model calls or production records were used. Local isolated backend was restarted on 8164; frontend remains on 3164. Production is not deployed by these checks.

Artifacts: `F:/codex/drawing-preview-verification/`, including real SVG fixtures and `cad-both-desktop.png`, `cad-both-mobile.png`.

GitHub delivery confirmed: `44ca210` on `15090560507-spec/door-erp`, branch `feat/semicircle-handles-and-quote-form-improvements`.
