# Reference Workspace Verification

## Delivered

- Merged component references and the library into one workspace. Category tabs are exactly: 门扇款式, 拉手, 合页, 颜色, 门套款式, 花件. No texture tab; all-assets/history retain old records.
- Replaced five large role-selection cards with automatic category routing. Color has a target selector; each selected image can be reassigned independently. Selected names/thumbnails remain available across category changes.
- Image uploads and screenshot paste events inside the workspace save to the library and automatically select the result. Uploads capture category/role at start, prevent concurrent double submission, report partial failures and allow retry. Input/textarea/contenteditable pastes and non-image clipboard events are untouched.
- Kept history restoration and existing PSD downloads. New generation stays quick-only and preserves reference bindings.
- Backend filters/search accept old 门扇/款式 and 包套/门套 categories under their new labels without rewriting stored data. Legacy categories are still accessible through all-assets/history.

## Verification

- TypeScript no-emit check passed.
- 28 frontend Node tests passed, including category order/routing, historical aliases and clipboard deduplication/text-target tests.
- Category database/service tests passed (5); rendering-background regressions passed (12). All use isolated test data and mocked providers.
- Targeted lint: zero errors; eight image-element warnings (six retained image sites plus two new reference thumbnails).
- Mocked Chrome browser test passed: default 2K and explicit/history 4K quick submissions; exact six-category order; no old component card section; file upload auto-selection; one screenshot event produces one upload; handle/flower hardware routing; color trim assignment and reassignment to frame; old 包套 asset selection from 门套款式; text-target and plain-text paste unaffected; upload failure/retry; no unexpected API calls or page errors.
- Browser clipboard tests dispatch image ClipboardEvents, not modifications to the user's system clipboard. Real paid image generation is not invoked.
- Desktop 1600px and mobile 390px screenshots inspected. No horizontal mobile overflow. Artifacts: `F:/codex/reference-workspace-verification/`.
- Existing browser test command: `node tests/render-quick-only.cjs`; set `RENDER_TEST_URL` and optional `RENDER_TEST_ARTIFACTS`.

No production data changes or Tencent Cloud deployment were performed.
