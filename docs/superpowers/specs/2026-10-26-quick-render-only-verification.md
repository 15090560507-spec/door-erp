# Quick Render Only Verification

## Changes

The render page now has one primary generation action, `一键生成效果图`. New tasks always use quick mode, including when inputs are restored from old precise-mode history. Automatic resolution is 2K; explicit 1K/2K/4K selections remain available.

Removed page imports/state/actions for segmentation creation and editing, component regeneration, new segmented PSD generation, and the PSD conversion modal. Existing historical images/references remain accessible. Existing PSD URLs can still be downloaded without creating a new task. Historical segmented tasks are labelled as historical results.

Backend routes, stored data, templates, model configuration, component-reference uploads, line-art extraction/crop, and the drawing-page workflow are unchanged.

## Checks

- TypeScript `tsc --noEmit --incremental false`: passed.
- Targeted page ESLint: zero errors; six existing `no-img-element` warnings.
- Existing frontend Node regressions: 23 passed.
- `git diff --check`: passed.
- Chrome/Playwright `node tests/render-quick-only.cjs`: passed using mocked API routes only. No real model/provider calls or live data writes.
- Browser assertions: one generation button; removed segmentation/local regeneration/PSD conversion actions absent; missing line art and missing panel references validated; submitted default 2K, explicit 4K, and restored legacy-history 4K requests all use quick mode with one image and no segmentation ID; reference files remain attached; an existing PSD downloads directly.
- Desktop 1600px and mobile 390px generation controls were captured and inspected. No horizontal mobile overflow or page errors. No unexpected API requests.

Run against an existing local development server with `RENDER_TEST_URL` (default `http://127.0.0.1:3164`). Set `RENDER_TEST_ARTIFACTS` for optional screenshots. Local verification artifacts: `F:/codex/quick-render-only-verification/`.

Tencent Cloud was not updated by this task.
