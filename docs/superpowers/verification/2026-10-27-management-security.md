# Management Security Verification

Policy: super administrators and UID A retain full business-management privileges. No production credentials or business records were modified. Account creation/deletion/password reset remain super-admin-only; A can manage business grants.

## Backend

Isolated `DATA_DIR=F:/codex/management-security-tests`; temporary databases for test fixtures.

```powershell
../.venv/Scripts/python.exe -m unittest test_management_security test_operations_workflow test_sales_order_receipts test_sales_order_fulfillment_bridge test_work_package_dependencies test_bom_api test_bom_versions test_hierarchical_bom test_production_inventory_positions test_door_piecework -v
../.venv/Scripts/python.exe test_security_phase1.py
../.venv/Scripts/python.exe test_inventory_api.py
```

- Combined unittest run: 63 passed, including 12 new security tests.
- Existing account-security script: 12 passed.
- Existing inventory API script: 18 passed.
- All 127 management route/method policies covered; unknown policies deny access.
- Fake approver text denied with no shipment or stock movement; explicit approval stores real UID, reason and debt amounts.
- Existing JWT grants/revocation use current server storage; permission claims in a signed token cannot override the user database.
- Frozen payroll rejects writes/recalculation even for A. Reopening needs the dedicated grant plus a reason, clears approval fields and cannot jump straight to approval.
- Permission/password/account updates retain grant history; same-process managers share a per-file write lock. This does not solve multi-process JSON writes.

## Frontend

```powershell
node --test src/lib/*.test.ts
node node_modules/typescript/bin/tsc --noEmit
node tests/management-security.cjs
node tests/production-loading.cjs
```

- 56 unit tests passed; TypeScript passed.
- Targeted ESLint passed for new permission panel, payroll, auth/navigation helpers, BOM controls and API/types. Existing production page unused StageNotice/TechnicalEditor warnings remain.
- Five browser identities: A, payroll writer, payroll approver, ordinary entry user, ordinary shipper. All passed with no browser runtime errors.
- Verified permission editor, protected A grants, reasoned unlock, approved payroll read-only controls, unauthorized direct URL redirect before payroll fetch, and non-editable real shipping identity.
- Desktop (1600x1000) and mobile (390x900) screenshots inspected; payroll table scrolls within its container.
- Existing production loading regression passed, including stale response protection/cache/search. Existing mobile overflow of 209px remains outside this batch.

Browser artifacts: `F:/codex/management-security-browser/`. Browser API responses are mocked; backend behavior is separately exercised through real temporary SQLite/JSON stores. These tests are not a production penetration test or a cloud deployment check.

## Deployment

Build backend and frontend together. No schema/data deletion or permission bulk rewrite required. Refresh/relogin after deployment to refresh menus; backend revocations apply to subsequent requests immediately. Validate ordinary accounts and explicit grants before broad rollout. Keep `LEGACY_PRODUCTION_ENABLED=false`.
