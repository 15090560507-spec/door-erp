# Production Loading Verification

## Scope

No page layout, approval policy, financial rules, payroll transitions or database schema changes. Production read paths, order selection, embedded BOM scoping and temporary read caching only. User data/template changes were excluded.

## Results

- 45 backend tests passed: production loading, workflow stages, work-package dependencies, operations, sales receipts/fulfillment bridge, BOM API/version/hierarchy and inventory positions.
- 53 frontend library tests passed, including cache deduplication, expiry, bounded size, failure retry and invalidation while a previous request is in flight.
- TypeScript noEmit passed.
- Targeted ESLint: no errors; two existing unused production components remain warnings.
- Production browser regression passed with mocked APIs and no production writes. Verified order list appears before the delayed pending-release request completes; old order responses cannot overwrite the latest selection; first door uses the combined response; a door outside the global first 100 gets its own BOM; embedded BOM sends no global workbench request; repeat selection reuses a short-lived page cache; a fast search word sends one list request without reloading people/dashboard; refresh invalidates cached selection; failed selection retries.
- Desktop screenshot inspected. Existing 390px narrow-screen layout overflow is 209px; recorded as an open UI issue, not claimed as fixed.
- Isolated 30-work-package benchmark from original HEAD versus repaired code: 55 -> 2 database connections; single-run approximately 49ms -> 3.3ms. Unit runs vary (roughly 3-5ms after repair). These are local results, not cloud end-to-end latency guarantees.
- Request/cache/navigation operations do not invoke CAD or AI generation.

## Known Baseline Problems

- test_calculation_workflow.CalculationWorkflowTest.test_calculation_is_one_to_many_and_gates_preparation still expects preparation while the existing workflow emits calculation. Reproduced with the original HEAD repository class.
- The legacy test_fulfillment_center.py script passes its first 11 checks and then indexes an empty work-package list. The same IndexError was reproduced with the original HEAD class. It is not included in the 45 passing checks.

Neither issue was hidden by changing business rules or rewriting old expectations. Full ERP readiness is not certified by these checks.

## Audit Evidence

Isolated probes confirmed that an ordinary entry role can modify approved payroll (HTTP 200), unlock a payroll period (HTTP 200), and create an authorized unpaid shipment by supplying arbitrary authorization text (authorized=1). No real orders, employees or wages were changed. See ../../2026-10-27-erp-readiness-review.md for prioritized findings and recommendations.

Local screenshots: F:/codex/production-loading-verification. Local frontend: http://127.0.0.1:3164; isolated backend: http://127.0.0.1:8164.

## Deployment

Build backend and frontend, then recreate those services and restart https-proxy. No data deletion, volume cleanup or schema migration is required. Do not enable more JSON-writing worker processes as a performance workaround. Cloud logs and response timings should be checked after deployment; no direct cloud access was used for this review.
