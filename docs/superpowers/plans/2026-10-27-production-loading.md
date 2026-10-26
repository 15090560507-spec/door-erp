# Production Loading Implementation Plan

**Goal:** Faster, race-safe production order selection without altering business rules.
**Spec:** ../specs/2026-10-27-production-loading-design.md
**Stack:** Next.js client components, Axios, FastAPI, SQLite.

- [x] Add isolated baseline tests for connections, dependency batching and combined order loading.
- [x] Optimize detail reads and add backward-compatible combined selection response; avoid duplicate pending scans.
- [x] Separate list/overview loading; debounce search; add page-local bounded cache and latest-selection guards.
- [x] Bind embedded BOM directly to its door; preserve standalone behavior.
- [x] Verify frontend units, backend workflows, browser races, search request counts and mutations.
- [x] Write evidence-based ERP risk report and scoped verification. Commit/push status and cloud commands are confirmed in delivery.
