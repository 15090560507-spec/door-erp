# Floating Preview Correction

**User requirement:** The preview must float without reserving any form space and must be freely draggable.

- [x] Portal the existing preview to the document body; remove reserved grid/sticky layout at every viewport size.
- [x] Add pointer-captured mouse/touch dragging from the title, frame-batched movement, viewport bounds, keyboard movement and resize/content-size clamping.
- [x] Allow collapse/expand to uncover inputs; pause queued automatic work while collapsed. Preserve existing opt-in/debounce/cache behavior.
- [x] Verify dragging, viewport resize, scrolling, form width, minimizing, mobile interaction and previous preview/quote regressions.
- [ ] Commit, push and provide guarded Tencent Cloud commands.
