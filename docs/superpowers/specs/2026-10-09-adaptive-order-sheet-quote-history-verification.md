# Adaptive Order Sheet and Quote History Verification

Date: 2026-10-09

## Implemented Behavior

- Door geometry and annotations remain at their original CAD coordinates and sizes.
  Only the ORDER_FORM template, populated attributes and owned manufacturing notes
  are reflowed around the generated drawing bounds.
- Logo geometry is uniformly scaled. Existing fonts, metadata and full legal text
  are preserved. Long notes and legal remarks wrap within the available width.
- Unsupported templates retain their existing layout and report a warning in the
  generation log and X-CAD-Layout-Warning response header. Simple products without
  door geometry retain their existing sheet.
- The layout version participates in the generated-output cache identity.
- Quote storage has no 50-record retention policy. The old list endpoint returned
  only 50 records; it now exposes filtered pagination over the complete collection.
- Quote history supports whole-collection search, date filtering, totals, page-scoped
  selection, retry and returning to the preceding page after deleting the last page.
- Unreadable quote files raise an error instead of becoming an empty collection
  that a later write could overwrite.

## Automated Checks

From backend, with an isolated DATA_DIR and dependency folder:

```powershell
python -m pytest test_quote_history.py test_quote_multi_door.py test_cad_order_layout.py test_cad_sheet_jpg.py -q
```

Result: **29 passed, 14 subtests passed**. Three dependency/application deprecation
warnings remain. Four actual generated door variants were compared against the
same generation with adaptive layout disabled. Non-sheet entity DXF tags match
exactly, and adapted documents have no CAD audit errors.

The complete option regression suite reports **389 PASS / 9 FAIL**. Running the
same suite with adaptive layout disabled reports the same **389 PASS / 9 FAIL**.
The unchanged failures concern transom dividers/flowers, back-view frame mirroring,
cumulative dimension offsets and integrated-door transom/frame rules. No new
failure was observed; these nine existing issues are not repaired by this batch.

Frontend checks:

```powershell
npx tsc --noEmit
npx eslint src/components/QuoteHistoryModal.tsx src/lib/quoteApi.ts src/lib/quoteTypes.ts src/app/quote/page.tsx
node tools/verify_quote_history.mjs
```

TypeScript and scoped ESLint pass. Playwright passes at 1440 x 1000 and 390 x 844:
121 mock quotes, three pages, oldest-record search, resetting selection, repeated
filter clearing, load errors distinct from empty history, retry, and deletion of
the final 21 records followed by a return to page two. No browser page errors.
API interception ensures that UI checks do not modify business data.

`git diff --check` passes. Existing user-account data changes and `.superpowers/`
are excluded from this delivery.

## Visual Checks and Limits

Local artifacts are under `F:/codex/adaptive-sheet-verification`:

- `adaptive-0.dxf` through `adaptive-3.dxf`: final generated CAD samples.
- `before-0.jpg` / `after-0.jpg` through four before/after pairs.
- `history-1440.png`, `history-390.png`: quote history screenshots.
- `cad-baseline.log`: option regression with adaptive layout disabled.

Visual inspection caught and corrected legal remarks overflowing into the right
table and column misalignment in the history modal. Small/front-only layouts may
retain minimum-width whitespace so that metadata stays usable.

The comparison JPGs use the existing ezdxf/matplotlib renderer. They are layout
checks, **not native AutoCAD plot verification**. Native AutoCAD printing was not
retested in this batch. The existing 5940 x 4200 landscape, centered monochrome
print profile is unchanged. Paper-aspect letterboxing can remain.

No cloud database contents were inspected, no production quotes were deleted,
and no paid image-generation calls were made.
