# Unified Reference Workspace Implementation Plan

> **For agentic workers:** Implement and verify task-by-task.

**Goal:** Merge reference inputs/library with six ordered categories and reliable screenshot paste uploads.

**Architecture:** Retain reference-group API bindings. Add small category/clipboard helpers, compatible backend alias filtering, and consolidate the existing page workflow without changing generation logic.

**Tech Stack:** React/Next.js, TypeScript/Node tests, Python unittest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-26-reference-workspace-design.md`

- [x] Inspect current category, role binding, upload and paste paths; capture approved category order.
- [x] Add category/clipboard helpers and regression tests, plus backend alias-filter compatibility.
- [x] Merge page controls; implement upload-and-select, area paste handling, thumbnails and target adjustment.
- [x] Run focused backend/frontend checks and mocked desktop/mobile browser tests, including quick-only regression.
- [ ] Review, push GitHub, and provide Tencent Cloud commands with the delivery.
