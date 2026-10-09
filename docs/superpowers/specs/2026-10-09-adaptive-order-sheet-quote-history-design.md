# Adaptive Order Sheet and Complete Quote History

Date: 2026-10-09

## Confirmed Scope

This batch addresses two existing workflows: generated CAD order-sheet layout
and access to all saved quotes. It does not change door construction rules,
AI model integration, image generation, or the user's CAD printing profile.

The latest annotated screenshot defines the layout boundary:

- Red box: front/back door geometry, dimension annotations and view labels.
  Preserve their CAD dimensions, proportions, text heights and relative positions.
- Green box: manufacturing notes above the drawings, including trim and handle
  specifications. Adapt their placement, wrapping and text size.
- Outer frame: resize and reflow the sheet metadata around the drawing content
  rather than scaling the doors to fill a fixed template.

## Investigation

`backend/drawing.py` fills the existing template and draws doors at their actual
dimensions. It does not currently resize the order-sheet layout to the drawing
content. One note conversion also uses a fixed MTEXT width of 6000 CAD units.

`backend/quote_routes.py` requests `get_all(limit=50)` for the quote list.
`backend/quote_database.py` stores the complete quote collection without a
50-record retention limit. The history modal searches only those loaded records.
Local inspection does not establish the contents of the deployed cloud database.

## CAD Layout Design

### Ownership and Geometry Invariants

Capture generated drawing entities separately from template entities. Compute
the visible drawing bounds from the generated front/back geometry, annotations
and labels, including resolved INSERT and DIMENSION geometry. Ignore unrelated
template graphics and unused block definitions when sizing the drawing area.

The protected drawing group may receive one common translation. It must never
receive scaling, stretching, rotation, separate view movement or dimension
recalculation as part of sheet layout. Door dimensions, radii, insertion scales,
dimension values and annotation heights must be identical before and after layout.

Manufacturing notes must be identified by their source/ownership, not their color.
Green CAD dimension lines in the red box are protected drawing entities; they are
not the adaptable notes in the green box.

### Content-Aware Sheet

Retain the existing side-by-side front/back composition. Size the drawing area
from its actual content bounds with clearance for annotations. Reflow the header,
logo, right-hand specification table, manufacturing notes, legal remarks and
signature/footer rows around this area.

Preserve all metadata and note contents. Manufacturing notes use the available
width, wrap into additional lines and adjust their text height within a readable
range. Prefer additional rows before reducing text height below the sheet's
readability floor. Preserve text styles and font references; do not replace CAD
fonts or distort the logo.

The right-hand table and long remarks establish minimum sheet dimensions. Reduce
unnecessary blank space, but do not promise an exact fit to the red box at the
expense of cropped text, overlapping cells or unreadable table rows.

Keep the supported ORDER_FORM/ORDERFORM identity and ensure its outer boundary
matches the new sheet. Existing JPG/native-print window discovery must select
that updated boundary. Keep the user's 5940 x 4200 landscape, fit-to-paper,
centered monochrome printing profile. Paper-aspect letterboxing is separate from
the CAD sheet layout and may remain.

### Integration and Failure Handling

Use a focused layout helper after door generation and occlusion, before writing
the DXF. Reuse the same final DXF for preview, download and printing. Invalidate
affected generated-output caches when the layout algorithm changes.

Support front-only views, simple products, trim/transom variations and long notes.
For an unsupported template or unresolved layout ownership, retain the existing
sheet and expose a layout warning through the generation response. Never modify
door geometry to compensate for a missing frame or invalid bounds.

## Quote History Design

### Storage and API

Keep the existing full-collection persistence and atomic backup behavior.
Pagination is an access mechanism, not a retention policy. Existing explicitly
requested deletion remains supported; do not introduce automatic deletion.

Extend `GET /api/quotes` with `limit`, `offset`, `q` and `quoteDate` parameters.
Use a default page size of 50 and a maximum requested page size of 200. Return
`quotes`, `total`, `limit` and `offset`, where `total` is the number of records
matching the filters before pagination.

Filter the entire stored collection before selecting the page. Search customer,
project, quote identifier and names/sizes across all door groups and quote items,
not just the first displayed door. Preserve newest-first ordering and the existing
lightweight summaries. Preserve full-record loading for editing and existing
database helper compatibility.

### Interface

Rename both the entry button and dialog title from recent quotes to quote history.
Show the matching record total and previous/next pagination controls. Search and
date filtering operate across the whole database and reset to the first page.

Display loading and request errors explicitly, with retry available. A failed
request must not appear as an empty history. Prevent stale responses from
replacing results from newer filter/page requests.

Selection is restricted to the current page. Label select-all accordingly and
clear selections on page/filter changes. Preserve explicit confirmation for
deletion. After deletion, reload results and move back a page if the current last
page becomes empty.

## Verification and Acceptance

- Compare protected drawing entities before/after layout, subtracting only the
  common translation. Verify exact CAD geometry and unchanged annotation values.
- Exercise small single doors, wide double doors, tall doors, trim/transom and
  portal variants, front-only views, simple products and long manufacturing notes.
- Verify frame containment, no drawing/table/note overlap, readable wrapping,
  unchanged font references and no missing metadata.
- Confirm updated ORDER_FORM print bounds and unchanged printing profile. Inspect
  exported preview/JPG samples; do not equate a browser rasterizer with AutoCAD.
- With 121 isolated test quotes, verify pages of 50, 50 and 21, correct totals,
  search for records beyond the first page, secondary-door search and date filters.
- Verify creation/editing never removes older quotes and existing summary/full
  record behavior remains compatible. Use temporary storage, not business data.
- Check history loading/error/retry, pagination and page-scoped deletion in the UI.
- Run focused tests followed by relevant CAD and quote regressions; report any
  pre-existing failures separately from new regressions.

## Workflow Status

- [x] Repository and root-cause investigation.
- [x] Visual boundaries clarified using the user's screenshots.
- [x] Content-aware layout chosen over scaling the whole sheet or the doors.
- [x] Design confirmed in conversation.
- [x] Written specification and self-review for scope and consistency.
- [x] User review of this written specification, approved by the subsequent request to continue adjusting.
- [x] Implementation plan.
- [x] Implementation and verification; delivery is tracked in the implementation plan.

Delivery follows the user's standing request to push changes to
`15090560507-spec/door-erp`, branch
`feat/semicircle-handles-and-quote-form-improvements`. Unrelated local user-data
changes are excluded from commits.
