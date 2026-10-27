# Direct Procurement Verification

## Delivered
- Page top-right New Purchase Order, separate from demand merging.
- Free-entry/searchable supplier and material name; existing material specifications/units read-only, with an explicit new-spec action.
- Draft creation atomically resolves/creates master records and active supplier relationships. No separate master-write API permission is granted to buyers.
- Confirmation publishes supplier-specific prices/history, preserving purchase-unit conversion, tax and other relationship metadata. Multi-price lines retain their snapshots and publish a quantity-weighted reference.
- Actor-scoped request keys make unchanged failed-response retries idempotent; changed payloads need a new key.
- Inventory schema v2 adds nullable supplier identity and request metadata, preserving legacy text-only orders without guessing their supplier identity.

## Verification
- New backend unittest suite: 13 passed, including concurrent retries, failure rollback, real v1-to-v2 additive migration, price conversion and HTTP permission boundaries.
- Existing management-security suite: 12 passed.
- Existing inventory-purchasing script: 14 passed.
- Existing inventory API script: 18 passed.
- Frontend unit tests: 59 passed.
- TypeScript noEmit and targeted ESLint: passed.
- Playwright tests/purchase-catalog.cjs: passed at desktop 1600x1000 and mobile 390x844. Tests cover cancel without writes, name/code/spec search, supplier price conversion, manual overrides, new-item fields, retry key stability and separate demand merging.
- Screenshots inspected at F:/codex/purchase-catalog-browser/desktop.png and mobile.png; no dialog horizontal overflow.

## Boundaries
- New materials start as active purchasable raw materials; richer classification, warehouse defaults and supplier contacts remain editable in existing master-data screens.
- Supplier price history uses the existing inventory_supplier_item_prices table. Legacy orders without supplier identity do not retroactively modify supplier prices.
- No production credentials, customer data or CAD templates were changed. A production Next build was not run against the shared active development output; TypeScript, lint and browser checks were used locally.
