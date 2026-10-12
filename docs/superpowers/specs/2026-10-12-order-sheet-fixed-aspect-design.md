# Fixed-Aspect CAD Order Sheet Correction

Date: 2026-10-12

## Confirmed Requirements

The user rejected the independently resized order-sheet width and height from
the previous batch and confirmed the following correction:

- Preserve the original CAD template outer-frame width/height ratio exactly.
- Permit the frame to grow or shrink only by one uniform scale factor.
- Do not change door geometry or dimension annotations: coordinates, dimensions,
  relative view positions, font heights and dimension values remain unchanged.
- Adapt the manufacturing explanations identified by the BZ note ownership
  (the green box in the user's screenshot). Choose the largest fitting uniform
  font height, suitable wrapping and placement to reduce empty space in their
  allocated region. Do not distort glyphs, truncate text or overlap the doors.

This specification supersedes the independent frame-width/frame-height sizing
in the 2026-10-09 adaptive layout design. Quote history is not part of this fix.

## Root Cause and Alternatives

`backend/cad_order_layout.py` computes `left_width` and `new_height` independently
and maps the template through different horizontal and vertical partitions.
There is no original-frame aspect-ratio constraint. The manufacturing-note font
height is also capped before the available region is considered, leaving room
unused. Existing tests assert compaction but do not assert the frame ratio.

Chosen approach: fit the original template to the protected drawing bounds with
one uniform scale for its frame/grid geometry, then independently fit the owned
manufacturing notes into their reserved space. This minimizes changes to the
template and prevents another distorted frame.

Rejected alternative: keep the original absolute frame dimensions. It preserves
the ratio but leaves unnecessary blank space for small doors and cannot fit very
large drawings without scaling the doors, which is forbidden.

## Layout Rules

Use the original closed ORDER_FORM/ORDERFORM outer rectangle as the aspect-ratio
source. The paper/output aspect ratio is not a substitute for the template ratio.
Keep the existing landscape, centered monochrome printing profile unchanged.

Calculate the protected drawing bounds using the existing resolved CAD entities.
Determine a uniform frame scale that contains these bounds, the manufacturing-note
region, metadata, footer and safe clearances. Translate the sheet around the
stationary drawings rather than translating/scaling the drawings themselves.
Do not impose an upper scale cap that could clip a large door.

Preserve the template grid, logo and checkbox geometry through uniform scaling.
Keep all populated metadata and font/style references. Fit long attribute values
inside their cells without changing their content or stretching glyphs.

The note region spans the usable left-panel width above the protected drawings
and below the header, with clearances on all sides. Recompute wrapping as the
candidate font height changes. Choose the largest fitting font height based on
both the region width and height; width alone must not determine fit. Place the
result within that region, preserving paragraph order and all text. A short line
may retain whitespace when enlarging it would exceed the region's height; do not
spread letters or distort text merely to force full coverage.

If notes cannot fit at the readability floor, increase the overall sheet scale
and retry instead of hiding content or shrinking the doors. Keep unsupported
templates on the existing warning/fallback path, with transformations staged
before commit to prevent partial updates.

Update the layout cache version so cached independently stretched frames cannot
appear after the correction is deployed. Preview, DXF download and sheet printing
must use the same final layout.

## Verification

- Assert outer width/height equals the original template ratio within numeric
  tolerance for single-view, double-view, wide, tall and transom/trim cases.
- Compare protected entity DXF attributes/tags before and after layout exactly.
- Assert the drawing and note bounds lie inside their reserved regions, with no
  note/header/table/drawing overlap and no text loss.
- Exercise short notes, multiline notes, long Chinese text, mixed Latin/numeric
  specifications and no-note drawings. Verify a larger candidate font height
  would exceed the selected region, within fitting tolerance.
- Check metadata contents, font references, logo aspect ratio, fallback behavior,
  print-window discovery and CAD document audit.
- Inspect before/after output for several real generated doors. Rendered JPGs
  are layout checks, not proof of native AutoCAD printing.
- Run the focused layout/printing tests and compare any full CAD suite failures
  with the existing baseline. Do not claim unrelated failures have been fixed.

## Workflow Status

- [x] Repository/root-cause review.
- [x] Alternatives and correction presented.
- [x] User confirmed uniform frame scaling with fixed aspect ratio.
- [x] Written specification and consistency review.
- [ ] User review of the written specification.
- [ ] Implementation plan, correction, verification and GitHub delivery.

Exclude the existing `data/users_database.json` changes and `.superpowers/` from
commits. Delivery uses the previously authorized GitHub repository and branch.
