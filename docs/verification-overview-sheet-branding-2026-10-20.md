# Overview Navigation and Blank Sheet Branding

## Delivered Behavior

- Overview cards open the same task in the drawing module. The module-reset timer consumes the pending task ID before the existing loader runs.
- Added exact preset `众鼎门业`; existing default, `杭州兰庭新贵门业`, and custom entry remain available.
- Sheet TT is centered in its original cell, with proportional font reduction for long titles.
- Only `浙江西州将军铜门订货单` retains the original logo and brand name. Nondefault titles leave the original top-left cell blank, without merging cells or removing their boundaries.
- Branding is applied to a private generated document after sheet layout. The cache layout version changed so old cached output cannot override the new rule.
- Mobile navigation closes the drawer before the unsaved guard opens. Keyboard actions on a nested quote-status button no longer activate the task card.

## Verification

- Initial backend test failed for the missing branding module; initial browser test failed because overview cards did not expose drawing actions.
- Focused backend suites: **50 passed, 31 subtests passed**. Suites cover branding, layout, editable downloads, sheet JPG, line-art geometry/ratio, and multi-door quotes.
- Real template checks preserve original grid DXF tags and all protected drawing entities. The small LINE inside the logo is decorative, not a grid line, and is removed with the logo.
- Actual generation covers default, 众鼎, 兰庭, a long custom title, and a simple-product sheet. DXF audits pass; shared-template isolation and blank-title fallback pass.
- Four generated samples include source DXF, editable DXF, SVG door preview, printed JPG and editable-DXF JPG in `F:/codex/overview-branding-verification`.
- Title/brand areas are pixel-identical before and after editable export. Whole-sheet JPG differences are limited to an 8x16-pixel existing checkbox area, at most 2/255 intensity and mean absolute error 0.000023/255. No title, grid, door or dimension displacement was observed.
- Actual JPGs inspected for default, 众鼎, 兰庭 and long custom titles. The browser SVG remains the existing door-only preview; it intentionally does not display the sheet header.
- Playwright at **1440px and 390px** passes pointer/keyboard task entry, two different task IDs (including an approved task), drawing controls, preset/custom title entry, cancel/discard navigation guard, save to the same ID without status changes, independent quote-status click/Enter, and canceled deletion. No browser page errors.
- TypeScript passes. Scoped ESLint reports 0 errors and 5 existing dashboard warnings (unused variables, image optimization, and one effect dependency).
- Local backend restarted on port 8123 and health checked; frontend remains at `http://127.0.0.1:3123/dashboard`. Both use isolated local test data, not cloud business records.

## Scope and Limits

- No paid generation calls, production data edits or Tencent Cloud deployment.
- Existing saved DXF/JPG files are not rewritten; regenerate them to use the new title rules.
- No AutoCAD application/native plotting session was run for this change. Artifact validation uses the existing DXF pipeline and JPG renderer; this work does not claim to change its printing engine.
- The full legacy CAD baseline was not rerun. This change does not claim to repair its previously known failures.
- Preexisting `data/users_database.json` and `.superpowers/` changes are excluded from delivery.

## Delivery

Implementation commit `2b0dffc` was pushed to `15090560507-spec/door-erp`, branch `feat/semicircle-handles-and-quote-form-improvements`.
