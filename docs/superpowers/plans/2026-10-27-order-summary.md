# Order Summary Implementation Plan

**Goal:** Make confirmed order details readable and scan-friendly without changing commercial behavior.
**Architecture:** Presentation-only React components and scoped CSS. A pure display resolver combines confirmed fields with frozen snapshot fallbacks; the existing APIs and pricing functions remain authoritative.
**Tech Stack:** Next.js client workspace, React, TypeScript, CSS grid/container queries, Node tests and Playwright.
**Spec:** ../specs/2026-10-27-order-summary-design.md (approved continuous-section design).

## Constraints

- Keep order/quote/receipt calculations, API payloads, permissions and stored snapshot data unchanged.
- Fonts: section 18px, row title 16px, body 14px, auxiliary 12px. Zero letter spacing. No viewport-scaled text.
- Five continuous sections; no new tabs, nested cards or unrelated layout refactoring.

## Tasks

- [ ] Add pure `salesOrderDisplay.ts` resolver and `salesOrderDisplay.test.ts`. Test confirmed technical/line/snapshot precedence, missing legacy fields and no mutation using `node --test src/lib/salesOrderDisplay.test.ts`.
- [ ] Update `OrderSummary.tsx` and `OrderLineDetails.tsx` to labelled sections, centered middle summaries, one parameter grid and collapsed source records. Keep `salesOrderChargeAmount(charge)` fallback and every existing action callback.
- [ ] Update `OrderAttachmentSummary.tsx`: one no-file message, populated categories only otherwise; retain download/error behavior.
- [ ] Replace only summary CSS rules in `globals.css`; use container queries for summary columns and preserve editor/shared component styles. Verify no clipping/overflow at desktop, 4K and mobile.
- [ ] Add `frontend/tests/order-summary.cjs` browser fixtures/assertions for source warnings, values, headers, section ordering, empty/populated attachments, callbacks and error states. Inspect screenshots.
- [ ] Run TypeScript, targeted ESLint, frontend unit tests and isolated order/receipt backend regressions. Document results, commit only scoped files, push the approved branch and provide Tencent Cloud commands.
