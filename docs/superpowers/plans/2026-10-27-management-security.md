# Management Security Implementation Plan

**Goal:** Close the three confirmed business-authorization gaps while retaining A's business-admin privileges.
**Spec:** ../specs/2026-10-27-management-security.md
**Stack:** FastAPI dependencies, SQLite transactions/events, Next.js permission-aware controls.

- [x] Add a canonical business permission catalog, role defaults and explicit per-user assignments; protect configuration and audit grants.
- [x] Enforce fail-closed route permissions across management APIs, replacing BOM's A-only gate.
- [x] Require explicit privileged debt release with server-derived identity and recorded amounts.
- [x] Freeze payroll outside draft; authorize/audit transitions and reasoned reopening.
- [x] Add permission configuration UI, per-module navigation and truthful approval/payroll controls.
- [x] Verify route coverage, spoofed identities, grants/revocation, A compatibility, approval states and browser workflows.
- [x] Update audit findings and verification evidence; prepare the scoped GitHub delivery and deployment commands.
