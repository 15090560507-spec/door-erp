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

- [x] Add `backend/test_quote_ai_permissions.py` with isolated `AiConfigManager` and TestClient; assert A GET/POST 200, ordinary GET/POST 403, anonymous 401, redacted key and unchanged key on blank update.
- [x] Run `python -m unittest test_quote_ai_permissions -v`; confirm A fails before the fix.
- [x] In `backend/quote_routes.py`, replace only the two AI-configuration dependencies with `require_business_admin`; generalize its denial message in `backend/auth.py`. Keep `require_super_admin` unchanged.
- [x] Rerun API tests and `test_management_security` / `test_reference_patterns`.

## Task 2: Configuration Dialog

- [x] Add `frontend/tests/quote-ai-config.cjs` covering A/admin entry, ordinary hidden entry, red read/save errors, disabled save after read failure, retry, key clearing and late-response isolation.
- [x] Gate the button/dialog in `frontend/src/app/quote/page.tsx` with existing `useAuth` and `isBusinessAdmin`.
- [x] Update `frontend/src/components/AiConfigModal.tsx`: loading/loaded state, success/error object, read retry, disabled fieldset/save while unavailable, cancellation guard and delayed-close cleanup.
- [x] Run browser test, `npx tsc --noEmit`, targeted ESLint and library tests.

## Task 3: Delivery

- [x] Record test results and inspect scoped diff. Implementation pushed as `c1bdaf8`; Tencent Cloud update commands are included below.

## Verification Results

- Confirmed pre-fix failures: account A GET returned 403; an ordinary account saw the configuration button.
- Post-fix backend: 31 tests passed (`test_quote_ai_permissions`, `test_management_security`, `test_reference_patterns`). Five focused authorization tests use a temporary configuration file and verify denied writes have no side effects.
- Frontend: 59 library tests passed; `tsc --noEmit` and targeted ESLint both passed without errors or warnings.
- Playwright: account A and super-administrator access, hidden ordinary-account entry, read retry, red read/save errors, disabled save until loaded, empty key on read, key clearing after save, duplicate-success save prevention and stale-read cleanup passed. Desktop 1440x1000 and mobile 390x900 screenshots inspected; no horizontal modal overflow or browser errors.
- Browser API responses were mocked. Backend authorization/configuration persistence used real FastAPI handlers and a temporary JSON store. No production credentials or live model inference were used; no paid AI calls occurred.
- Existing development server reused at http://127.0.0.1:3164. No production build or Tencent deployment was run locally.
- Artifacts: `F:/codex/quote-ai-config-browser/save-error-desktop.png` and `save-error-mobile.png`.

## Tencent Cloud Update

Run on the existing Ubuntu deployment. Rebuild both services; do not remove volumes or data.

```bash
bash <<'EOF'
set -euo pipefail
cd ~/door-erp
BRANCH=feat/semicircle-handles-and-quote-form-improvements
[ "$(git branch --show-current)" = "$BRANCH" ] || {
  echo "Branch mismatch; update stopped"
  exit 1
}
git pull --ff-only origin "$BRANCH"
sudo docker compose build backend frontend
sudo docker compose up -d --no-deps backend frontend
sudo docker compose restart https-proxy
sudo docker compose ps
EOF
```
