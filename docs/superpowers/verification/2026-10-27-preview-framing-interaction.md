# Preview Framing and Interaction Verification

## Scope

- Grouped door previews exclude order-form descendants, nearby general notes and table labels. Virtual dimension entities inherit their dimension layer, retaining measurement text.
- Legacy preview/render collectors and generated DXF geometry keep their previous behavior. Grouped SVG cache advances to v2.
- The lower preview has a stable canvas target. Its midpoint must enter the viewport before docking; scrolling back restores the previous floating size and position.
- Left drag pans the SVG. Right drag up zooms in and down zooms out, anchored at the starting pointer position, with uniform bounded scaling. Fit reset restores the selected view. Context menus are suppressed only inside the canvas.
- Canvas navigation and docking send no CAD or AI requests.

## Checks

- Backend preview/download tests: 17 passed.
- Backend quote, quantity, contour and history tests: 37 passed.
- Legacy CAD preview and mirrored fingerprint block checks: 6 passed.
- Frontend library tests: 50 passed.
- TypeScript noEmit: passed.
- ESLint on changed components/helpers/tests: passed.
- Browser regression with generated wide-front.svg: passed at desktop and 390px mobile widths. Covers actual half-canvas visibility, stable scroll position, window restoration, left pan, right zoom, fit reset, no extra generation requests, save/quote workflows and stale-request handling.
- Screenshots inspected: floating front view, panned/zoomed canvas, docked desktop and mobile views.
- Browser APIs mocked; no paid generation or production data writes.

Artifacts are local under F:/codex/preview-framing-browser and F:/codex/preview-framing-interaction. Local test page: http://127.0.0.1:3164.

## Deployment

Target: 15090560507-spec/door-erp, feat/semicircle-handles-and-quote-form-improvements.
Rebuild backend and frontend, then restart https-proxy. No schema migration, volume deletion or data cleanup is required. Confirm the pushed fix commit is present before rebuilding. Refresh the browser after deployment; previously generated SVGs must be refreshed once to use the corrected grouping.
