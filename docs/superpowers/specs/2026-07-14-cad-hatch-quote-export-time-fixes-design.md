# CAD Hatch, Quote Export, and Time Fixes

## Scope

This change fixes five existing behaviors without changing door geometry,
pricing calculations, or the quote template's A4 structure.

## CAD hatch definitions

- Copy the complete pattern line definition from the matching hatch in
  `template.dxf`, not only its name, scale, and angle.
- Preserve the source hatch metadata and transform copied pattern lines when a
  mirrored fill is required.
- Enable fill and regeneration headers in generated DXF documents.
- Keep hatches as editable HATCH entities; do not explode them into lines.

## Hardware masks

- Prefer the largest closed polyline found inside each hardware block as the
  wipeout outline.
- Tessellate curved entities when necessary.
- If no closed outline is available, derive a convex hull from block geometry.
- Retain the current bounding rectangle only as a final fallback.
- Apply block insertion scale, mirror, rotation, and translation to the mask.

## Optional quote project name

- Remove project-name validation in the quote page and quote database.
- Store an empty string when no project name is provided.
- Avoid redundant separators in quote history when the project name is empty.

## Excel layout

- Preserve the existing merged cells, borders, print area, and A4 page setup.
- Apply the configured Song-style font fallback to dynamic text cells.
- Wrap dynamic text and calculate row heights from display width.
- Increase dynamic column widths only within bounded limits; overflow continues
  by increasing row height rather than widening the A4 layout indefinitely.
- Apply the same workbook layout to Excel, JPG, and PDF export paths.

## Time handling

- Generate date-only defaults from the browser's local calendar date instead
  of slicing a UTC ISO timestamp.
- Use the same local-date helper for today's dashboard counts and export names.
- Generate task modification timestamps explicitly in Asia/Shanghai time.
- Continue storing rendering timestamps as UTC and displaying them in
  Asia/Shanghai.

## Verification

- Assert generated custom hatches retain the source pattern-line count and
  ANSI patterns retain their definitions.
- Assert block masks can use polygon outlines and remain on the mask layer.
- Assert quotes can be created without a project name.
- Assert long dynamic Excel text wraps and receives sufficient row height while
  the print area remains A1:J24.
- Build the frontend and run the existing CAD, quote, and security tests.
