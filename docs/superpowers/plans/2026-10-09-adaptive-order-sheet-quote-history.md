# Adaptive Order Sheet and Quote History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compact order sheets without scaling door entities, and expose all saved quotes through searchable pagination.

**Architecture:** Keep existing DXF generation and JSON quote persistence. Add an isolated content-aware template layout helper; add filtered database pagination and wire it into the existing history modal. Execute inline in the current session as requested; the named execution sub-skills are not installed on this host.

**Tech Stack:** Python, ezdxf, FastAPI, React, Next.js, TypeScript, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-adaptive-order-sheet-quote-history-design.md`

## Global Constraints

- No door geometry, annotation height, dimension value or insertion-scale changes.
- Identify adaptable notes by ownership/tag, not green entity color.
- Preserve ORDER_FORM/ORDERFORM, text styles and the 5940 x 4200 printing profile.
- Quote page size defaults to 50, maximum 200; no automatic retention deletion.
- Tests use isolated data; exclude `data/users_database.json` and `.superpowers/`.
- Push delivery to `feat/semicircle-handles-and-quote-form-improvements`.

## Task 1: Complete Quote Query

Files: `backend/quote_database.py`, `backend/quote_routes.py`, `backend/test_quote_history.py`.

Interface: `QuoteDatabaseManager.get_page(limit=50, offset=0, q='', quote_date='') -> dict` returns quotes/total/limit/offset. `get_all(limit)` delegates to this query and retains its list return type.

- [x] Add temporary-file tests with 121 records: three pages, reverse order, old-record search, second-group size/name search, date filter, invalid page arguments and create/update retention.
  ```python
  page = database.get_page(limit=50, offset=100)
  assert page['total'] == 121
  assert len(page['quotes']) == 21
  assert database.get_page(q='oldest')['quotes'][0]['id'] == 1
  ```
- [x] Run initial quote tests and verify the missing `get_page` failure; use pytest for the combined regression run.
- [x] Filter complete records before slicing; reuse existing summary selection logic. Validate `limit` and `offset` with FastAPI Query and manager checks.
  ```python
  return {'quotes': summaries, 'total': len(matches), 'limit': limit, 'offset': offset}
  ```
- [x] Run focused quote history and existing multi-door quote tests.

## Task 2: History Interface

Files: `frontend/src/lib/quoteTypes.ts`, `frontend/src/lib/quoteApi.ts`, `frontend/src/components/QuoteHistoryModal.tsx`, `frontend/src/app/quote/page.tsx`.

Interface: `getQuotes(params, signal?) -> Promise<QuoteListResponse>` supplies typed page/filter parameters and supports AbortSignal.

- [x] Add response offset/limit types and send query parameters through Axios.
  ```typescript
  api.get<QuoteListResponse>('/quotes', { params, signal });
  ```
- [x] Replace local filtering with debounced server filters; use an effect-scoped AbortController to discard stale requests. Clear selections while page/filter requests change. Represent loading, load failure and mutation status independently.
- [x] Add total, range, page count, accessible previous/next icon controls, retry, page-scoped select-all and safe last-page adjustment after deletion. Rename the title/entry to quote history.
- [x] Run TypeScript and scoped ESLint. Use intercepted API responses in Playwright to verify desktop/mobile, page/filter queries, errors/retry and selection reset without touching business data.

## Task 3: Adaptive CAD Sheet

Files: create `backend/cad_order_layout.py`, create `backend/test_cad_order_layout.py`, modify `backend/drawing.py` and `backend/main.py`.

Interface: `adapt_order_sheet(doc, drawing_entities, notes) -> str | None`, returning a warning only when the existing template cannot safely be adapted. `ORDER_LAYOUT_VERSION` participates in CAD cache identity.

- [x] Write tests against the real template with synthetic drawing geometry and notes. Snapshot protected entity attributes before layout; assert identical after. Check smaller frame bounds, note wrapping and untouched samples outside the frame.
  ```python
  before = [entity.dxf.all_existing_dxf_attribs() for entity in drawings]
  warning = adapt_order_sheet(doc, drawings, notes)
  assert warning is None
  assert before == [entity.dxf.all_existing_dxf_attribs() for entity in drawings]
  ```
- [x] Run tests and verify the missing helper failure.
- [x] Discover the closed outer rectangle and grid partitions from ORDER_FORM geometry. Validate supported template shape before changing anything. Derive bounds from generated entities only, using ezdxf bbox with resolved blocks/dimensions.
- [x] Reflow grid coordinates into content-aware left-panel/header/footer/right-table partitions. Scale metadata uniformly, preserve logo aspect ratio, fit attribute text within cells, and wrap the owned BZ note above the drawing bounds. Keep actual door entities at their original coordinates.
- [x] Stage template transformations on copies before replacing entities so unsupported templates keep their old layout. Preserve block name, populated attributes, fonts and static remarks. Handle no-door simple products by retaining their existing sheet.
- [x] Capture drawing entities before/after generation and owned BZ MTEXT separately; call layout after occlusion, before writing. Include algorithm version in cache keys and surface fallback warning in CAD response headers.
- [x] Run layout and print-window tests; generate real door variants and compare protected entity snapshots with layout disabled. Verify bounds/notes and no new CAD audit errors.

## Task 4: Verification and Delivery

Files: verification notes under `docs/superpowers/specs/`, update this checklist and spec status.

- [x] Inspect compact sheet preview/JPG and history desktop/mobile screenshots. Preserve native-print distinction and report unavailable AutoCAD verification explicitly.
- [x] Run relevant CAD and quote regressions; distinguish baseline failures from introduced failures.
- [x] Review `git diff --check`, stage only this batch, commit, push the authorized branch and confirm clean task-owned changes.

No paid image-generation calls are required for this batch.
