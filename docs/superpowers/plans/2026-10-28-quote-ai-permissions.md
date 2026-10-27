# Quote AI Configuration Permission Fix Implementation Plan

> Execute inline in the existing checkout; preserve unrelated account data and CAD templates.

**Goal:** Let super administrators and exact UID A configure quotation AI, with correct error feedback and no key disclosure.
**Architecture:** Reuse existing backend/frontend business-admin predicates; keep endpoint response contracts and credential handling unchanged. Add dialog loading and explicit feedback state.
**Tech Stack:** FastAPI, unittest, React, Next.js, Playwright.
**Spec:** docs/superpowers/specs/2026-10-28-quote-ai-permissions-design.md

## Global Constraints

- Only super administrators and exact UID A may read/write AI configuration.
- No inference calls, live API-key writes or changes to unrelated super-admin-only endpoints.
- Keep blank-key preservation and response redaction.

## Task 1: Authorization Regression

- [ ] Add `backend/test_quote_ai_permissions.py` with isolated `AiConfigManager` and TestClient; assert A GET/POST 200, ordinary GET/POST 403, anonymous 401, redacted key and unchanged key on blank update.
- [ ] Run `python -m unittest test_quote_ai_permissions -v`; confirm A fails before the fix.
- [ ] In `backend/quote_routes.py`, replace only the two AI-configuration dependencies with `require_business_admin`; generalize its denial message in `backend/auth.py`. Keep `require_super_admin` unchanged.
- [ ] Rerun API tests and `test_management_security` / `test_reference_patterns`.

## Task 2: Configuration Dialog

- [ ] Add `frontend/tests/quote-ai-config.cjs` covering A/admin entry, ordinary hidden entry, red read/save errors, disabled save after read failure, retry, key clearing and late-response isolation.
- [ ] Gate the button/dialog in `frontend/src/app/quote/page.tsx` with existing `useAuth` and `isBusinessAdmin`.
- [ ] Update `frontend/src/components/AiConfigModal.tsx`: loading/loaded state, success/error object, read retry, disabled fieldset/save while unavailable, cancellation guard and delayed-close cleanup.
- [ ] Run browser test, `npx tsc --noEmit`, targeted ESLint and library tests.

## Task 3: Delivery

- [ ] Record test results, inspect scoped diff, commit/push the approved branch and provide Tencent Cloud update commands.
