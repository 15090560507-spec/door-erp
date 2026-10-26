# Preview Resize and Docking Verification

## Behavior
- Default floating frame is 510x660px (1.5x the prior 340x440 frame), clamped to the viewport. Its first selected side is front.
- Plus/minus buttons scale the frame; the bottom-right grip resizes width and height independently with pointer capture and animation-frame batching. Dragging, keyboard movement, minimization and viewport bounds remain supported.
- The preview canvas flexes into the available body space, preserving geometry proportions and keeping dimension labels inside the frame.
- As the complete save action bar enters the lower preview region, the frame docks into the full-width home immediately beneath it. This threshold also works on short pages without an artificial spacer. Returning to the form restores the prior floating position and dimensions.
- Docking keeps side selection, automatic preview preference, cached SVG and last-success/error handling. Shared manual/automatic preview state replaces the duplicate result holders. Manual preview reveals the lower region; stale manual results are ignored if input geometry has changed.
- Dock transitions do not regenerate CAD, auto-save, or invoke an AI model. Input layout remains three columns without a reserved sidebar.

## Verification
- Frontend library unit tests: 47 passed, including default-size, resize bounds and docking threshold cases.
- TypeScript noEmit passed. Targeted ESLint: no errors; six existing dashboard warnings.
- Extended `quote-dual-trim.cjs` passed: exact 510x660 initial frame; front default; plus/minus sizing; corner shrink/expand; mouse/touch drag; mobile bounds; collapse pause/cache restore; full-width dock inside the home; restored floating coordinates/width and selected side; unchanged preview request count across docking.
- Existing quote/history/area/save/unsaved navigation and automatic-preview debounce/stale/error regressions passed. `render-quick-only.cjs` also passed.
- Desktop 1920x1100 and mobile 390x1000 screenshots inspected in `F:/codex/preview-resize-dock-verification/`. Default-front canvas is fully inside the floating frame, without clipped dimension labels. Docked preview expands below the action bar.
- Browser APIs/models were mocked using a real generated SVG fixture; production data and paid image generation were not used. Tests do not claim server-side performance or production deployment verification.
- Local preview remains at port 3164. Its owned development server uses Webpack to avoid the previously observed local Turbopack CSS cache issue; no production build configuration was changed.

GitHub delivery confirmed: `1d25234` on `15090560507-spec/door-erp`, branch `feat/semicircle-handles-and-quote-form-improvements`. Standard SSH succeeded after a 443-port timeout. Production deployment remains user-run.
