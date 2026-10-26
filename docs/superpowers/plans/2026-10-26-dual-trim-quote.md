# Dual Trim Quote Implementation Plan

**Goal:** Correct dual-trim outer-area quotes and navigate directly from a drawing to its quotation.

**Architecture:** Add a pure quote-only side-selection/linking helper; retain actual CAD trim metrics. Persist optional row-role and factor metadata in existing JSON quote records. Use exact task-ID navigation and existing save/guard mechanisms.

**Spec:** `docs/superpowers/specs/2026-10-26-dual-trim-quote-design.md`

- [x] Inspect pricing, contour metrics, quote persistence and drawing navigation; confirm net-area formula/default factor with user.
- [x] Implement/test pure dual-side pricing and linked-price helper.
- [x] Add metadata persistence/validation and task-specific latest quote lookup.
- [x] Integrate quote generation, factor editing, preservation of history, and drawing quote actions.
- [x] Fix quantity-preview wrapping without rounding or changing A4/column widths; verify standard and unusually long values.
- [x] Verify backend/frontend and mocked browser workflows, including exports and mobile.
- [ ] Review and push scoped changes; provide Tencent Cloud update commands.
