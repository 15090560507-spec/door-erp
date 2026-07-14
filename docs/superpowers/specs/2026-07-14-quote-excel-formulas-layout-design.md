# Quote Excel Formulas And Layout Design

## Goal

Keep exported quote workbooks editable in Excel and WPS. When a salesperson changes dimensions, quantity, or unit price, every derived amount must recalculate automatically. Long product names and numeric quantities must remain fully visible without changing the existing A4 quote structure.

## Scope

- Modify only the quote Excel generator and its automated tests.
- Preserve `template.xlsx`, the `A1:J24` print area, merged cells, colors, borders, and business fields.
- Do not change frontend quote calculations, quote database data, JPG/PDF routes, or pricing rules.

## Formula Model

- Rows `9:16` remain the eight quote detail rows.
- Area-unit quantities use a formula based on width and height when no explicit quantity is supplied.
- Explicit quantities remain editable numeric inputs because they are source data, not derived values.
- Detail amount cells `J9:J16` use `ROUND(quantity * unit price, 0)` formulas.
- Total cell `J17` uses `SUM(J9:J16)` instead of a static number.
- Uppercase amount cell `F18` references `J17`, rounds to whole yuan, converts with the Excel/WPS `DBNum2` number format, and displays `人民币...元整`.
- Workbook calculation mode remains automatic with full recalculation requested when the file opens.

## Layout Rules

- Product names in merged cells `B:C` use wrapped text and a conservative merged-width estimate that accounts for Chinese double-width characters and cell padding.
- Detail row height is calculated from the estimated wrapped line count and never falls below the template minimum.
- Quantity column `H` is widened enough for decimal area quantities and uses a compact numeric format that avoids `####` and unnecessary trailing zeroes.
- Width, height, unit price, line amount, total, and uppercase amount receive explicit number/alignment formats while preserving the template's border and fill styles.
- Column growth is bounded so the print area remains one A4 page wide.

## Error And Compatibility Handling

- Empty detail rows remain blank rather than displaying zero values.
- Empty width or height leaves a calculated area quantity blank.
- Empty quantity or unit price leaves the detail amount blank.
- Formula syntax uses functions supported by both current Excel and WPS (`IF`, `OR`, `ROUND`, `SUM`, `TEXT`).
- LibreOffice used by server-side JPG/PDF export is instructed to recalculate formulas when opening the workbook.

## Verification

- Assert formulas exist in detail amounts, total, and uppercase amount cells.
- Assert long product names enable wrapping and increase row height.
- Assert quantity column width and numeric format prevent hash overflow for representative decimal areas.
- Assert the print area and fit-to-page settings remain unchanged.
- Run the quote renderer regression suite and frontend production build.
