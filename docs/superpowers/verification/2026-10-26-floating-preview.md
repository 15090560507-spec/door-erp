# Floating Preview Verification

## Correction
- The preview is portaled to `document.body` and fixed to viewport coordinates. The drawing workspace no longer reserves a grid column or an in-flow preview region, on desktop or mobile.
- Dragging the title works with primary mouse/touch pointers using pointer capture. Pointer movement is batched per animation frame; SVG markup, generation queue and form data are unchanged during dragging.
- Position is bounded to the viewport with an 8px margin. ResizeObserver and viewport resize re-clamp it when the screen or preview content changes. Arrow keys also move the focused handle.
- Collapse/expand leaves a small movable title bar. Collapsed previews cancel pending automatic work; restoring reuses the existing bounded cache. Automatic preview remains opt-in and form saving is unchanged.
- The floating window remains below modal overlays; its full-screen preview still portals above it.

## Verification
- Frontend unit tests: 45 passed, including four new positioning tests.
- TypeScript noEmit and targeted ESLint passed, no errors or warnings in the new floating-window code.
- Browser regression passed: workspace width equals form width, preview is a fixed body child, exact mouse displacement, boundary limits, keyboard movement, fixed position on scroll, collapse/restore, paused auto-generation while minimized, cached restore, mobile resize and real CDP touch drag.
- Existing quote, save, line-art framing and automatic-preview debounce/stale/error/no-autosave regressions passed. Rendering workspace browser regression passed.
- Desktop 1920x1100 and mobile 390x1000 screenshots inspected: `F:/codex/floating-preview-verification/floating-dragged-desktop.png` and `live-preview-mobile.png`.
- Tests use mocked API/model calls and a real pre-generated CAD SVG fixture; no paid generation or production data changes.
- A stale local Turbopack CSS cache was identified during validation. Only the resolved `.next/dev` generated directory was moved to `F:/codex/next-dev-cache-before-floating-20261026-224348`; the owned development server was restarted and the browser tests rerun against freshly compiled styles. Source/data/templates were not removed.
