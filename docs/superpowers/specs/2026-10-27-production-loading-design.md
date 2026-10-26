# Production Loading Repair

Approved scope: keep layout and business rules unchanged; optimize loading, search and selection, and report ERP risks separately.

- Load the order list independently from slower overview/pending-release requests. Debounce search and discard superseded responses.
- Fetch an order and its first door in one HTTP request without transmitting the unused task snapshot. Keep a bounded, page-local 15-second selection cache, deduplicate in-flight requests, and invalidate it after local mutations or manual refresh.
- Immediately indicate the selected order, clear unrelated details and accept only the latest selection response. Do not allow old form controls to operate on a newly selected order.
- Embedded BOM must stay bound to its supplied door ID and must not request the global first 100 BOMs or substitute another door.
- Batch work-package dependency reads and reuse a scoped read connection for door details. No database schema or transaction/write-rule changes.
- Verify request counts, response races, cache invalidation, failures, data isolation and query/connection counts with temporary data. No production measurements or writes are claimed.
- Review permissions, financial release, payroll locking, status consistency and cross-store boundaries. Record reproducible evidence; do not silently change approval policy.
