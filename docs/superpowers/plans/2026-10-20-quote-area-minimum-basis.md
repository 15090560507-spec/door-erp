# Quote Area Minimum Basis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reproduced outer-area quantity override without changing the minimum-area business rule.

**Architecture:** Select the dimensions once inside the existing quote-row builder; use those dimensions for both displayed size and the minimum-area decision. Keep area formatting, exports and saved manual overrides unchanged.

**Tech Stack:** TypeScript/Next.js, Node assert, Playwright, existing quote export renderer.

**Spec:** `docs/superpowers/specs/2026-10-20-quote-area-minimum-basis-design.md`. User confirmed the written mode-specific correction in chat and requested implementation. Execute inline; the named execution sub-skills are unavailable.

## Global Constraints

- Outer mode uses outer dimensions; frame-plus-trim mode uses frame dimensions for the main-door row.
- Positive main-door area below 2 square meters retains the existing minimum of 2.
- Area precision stays four decimals; amount rounding, trim geometry and door counts stay unchanged.
- No historical quote/account data migration or cloud deployment.

## Task 1: Regression and Minimal Fix

Files: `tools/test_quote_quantities.mjs`, `frontend/src/app/quote/page.tsx`.

- [x] Extract existing top-level row-builder functions with the TypeScript AST in the test harness and reproduce the screenshot:
  ```js
  assert.equal(quote.quoteItemQuantityText(build(params, [], 'outerArea', 0)[0]), '2.1945');
  ```
- [x] Run the test against the old implementation and confirm failure (`2.0000` instead of `2.1945`), then select dimensions once:
  ```ts
  const quoteWidth = pricingMode === 'outerArea' ? outerWidth : frameWidth;
  const quoteHeight = pricingMode === 'outerArea' ? outerHeight : frameHeight;
  const rawDoorArea = quoteWidth * quoteHeight * 0.000001;
  ```
  Use them for row width/height and retain `rawDoorArea > 0 && rawDoorArea < 2 ? 2 : null`.
- [x] Run pure contracts covering outer/frame modes, below/exact/above 2, missing size, manual overrides and per-group multiplication.

## Task 2: UI and Export Verification

Files: new `tools/verify_quote_area_basis.mjs`; no new production UI or backend API.

- [x] Use isolated browser fixtures for the screenshot task and price 1480; assert 950 x 2310, 2.1945 and 3248 in outer mode, and 870 x 2270 with quantity 2 in frame mode. Switch back and ensure 2 is cleared.
- [x] Check two-door totals, manual quantity, legacy quantity preservation, clearing a stale quantity, save/reload, and generated HTML/JPG/PDF with the corrected value at desktop/mobile widths.
- [x] Run TypeScript, scoped lint, existing quantity browser checks and quote persistence/export backend regressions. Inspect screenshots and actual export.

## Task 3: Delivery

- [ ] Document checks and artifact locations, review the scoped diff, commit and push the authorized branch. Preserve unrelated user data and explain that old saved quotes require explicit review.
