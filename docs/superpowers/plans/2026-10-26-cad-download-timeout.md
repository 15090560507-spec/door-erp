# DXF Download Timeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate per-line DXF response overhead while preserving exported bytes and accurately reporting download timeouts.

**Architecture:** The CAD endpoint already holds the complete converted DXF in memory. Return those bytes in a regular Response with Content-Length and the existing headers. Apply CAD timeout copy in generateCad's error path without changing global request behavior.

**Tech Stack:** FastAPI, Starlette, Python unittest, Axios, TypeScript, Node test runner.

**Spec:** `docs/superpowers/specs/2026-10-26-cad-download-timeout-design.md`

## Global Constraints

- Keep the 60-second timeout, network-error handling, server-error details, preview, JPG export, and other endpoints unchanged.
- No changes to template assets, dimensions, flower blocks, sheet bursting, rendering, or production data.
- Commit only the approved files and push the existing branch.

## Task 1: Bounded DXF Transfer

**Files:** Modify `backend/main.py`; test `backend/test_cad_download.py`.

**Interfaces:** Consume `_cached_cad(req)` and `_cached_cad_download(key, dxf_bytes)` unchanged. Produce an application/octet-stream Response with identical download bytes, filename, cache headers, layout headers, and Content-Length.

- [x] Add a mocked route test with a payload containing at least 250,000 newline characters. Assert a materialized response body before executing ASGI, so the old implementation fails immediately rather than spending time iterating the sample.
- [x] Assert byte equality, Content-Length, filename, cache/layout headers, and exactly one `http.response.body` message; retain MISS/HIT and preview/JPG isolation coverage.
- [x] Run `python -m unittest test_cad_download.EditableSheetRouteTests` in the backend with an isolated DATA_DIR and confirm failure on the original route.
- [x] Remove the unused io and StreamingResponse imports and the BytesIO wrapper. Replace the response construction with:

```python
return Response(content=download_bytes, media_type="application/octet-stream", headers=headers)
```

  Keep the existing inline headers dictionary and filename construction in place.
- [x] Run editable-sheet, layout, branding, disc-panel, and CAD preview regressions. Check exported dimensions and flower geometry through their existing focused tests.

## Task 2: Accurate Timeout Copy

**Files:** Modify `frontend/src/lib/api.ts`; create `frontend/src/lib/api.test.ts`.

**Interfaces:** Keep `generateCad(formData): Promise<Blob>` and the original Axios error object. Set only `userMessage` on CAD timeout errors.

- [x] Add Node tests with temporary Axios adapters for ECONNABORTED, network failure, server error Blob details, and successful binary responses. Restore the adapter after every test.
- [x] Run `node --experimental-strip-types --test frontend/src/lib/api.test.ts`; confirm the CAD timeout-copy assertion fails on the original implementation.
- [x] Before existing Blob error parsing in generateCad, apply:

```typescript
if (axios.isAxiosError(error) && error.code === "ECONNABORTED") {
  requestError.userMessage = "DXF 文件生成或下载超时，请稍后重试";
}
```

- [x] Rerun the tests, TypeScript no-emit checking, and ESLint on both touched TypeScript files. Verify the shared 60000 timeout and non-CAD messages remain unchanged.

## Task 3: Review And Delivery

**Files:** Create `docs/superpowers/verification/2026-10-26-cad-download-timeout.md`; update this checklist.

- [x] Measure the complete response using a real generated DXF; compare byte identity, SHA-256, body-message count, and transfer-only overhead with the former implementation. Separate these numbers from actual cloud network throughput.
- [x] Review the scoped diff, run whitespace checks, and record exact results plus any remaining verification limits.
- [x] Stage only the two source files, two test files, and three repair documents; commit and push `feat/semicircle-handles-and-quote-form-improvements` to `15090560507-spec/door-erp`.
- [x] Report the commit and explain that the user still needs to deploy it to Tencent cloud before live retesting.
