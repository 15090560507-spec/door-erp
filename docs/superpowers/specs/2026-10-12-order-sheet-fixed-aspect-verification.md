# Fixed-Aspect Order Sheet Verification

Date: 2026-10-12

## Correction

The previous independent x/y mapping has been replaced by one uniform template
scale. The original ORDER_FORM rectangle ratio (approximately 1.4271593083)
remains unchanged. The grid, logo and checkbox geometry use the same scale.
The sheet is translated around stationary door drawings; door geometry, view
placement and dimension annotations are not scaled or moved.

Manufacturing notes now use their available left-panel region above the drawings.
A bounded search chooses the largest fitting font height using wrapped line
width and total block height. Font glyphs are not stretched. Paragraph contents
and ordering are preserved, and the sheet grows uniformly if notes cannot fit
at the minimum readable height. The previous note font-height cap is removed.
Long attribute values and legal remarks remain within their allocated regions.

The cache version is now `fixed-aspect-order-sheet-v2`, so newly generated output
cannot use the previous independently stretched sheet cache entries. Existing
saved DXF/JPG files are not rewritten; regenerate them to obtain the correction.
The user's printing profile is unchanged. This batch does not alter quotes,
render models or unrelated door construction rules.

## Test Evidence

The added ratio regression failed on all four synthetic variants before the fix:
ratios were approximately 0.991, 1.148, 4.681 and 0.871 rather than 1.427.

After the correction:

```powershell
python -m pytest test_cad_order_layout.py test_cad_sheet_jpg.py test_quote_history.py test_quote_multi_door.py -q
```

Result: **37 passed, 25 subtests passed**, with three existing deprecation warnings.
Checks include fixed frame/grid proportions, exact drawing DXF attributes/tags,
very wide/tall drawings, front-only views, text preservation, maximum fitting
note height, Chinese/Latin/multiline/empty notes, readable growth for long notes,
unsupported-template rollback and output-cache invalidation.

Four real door variants were generated with and without adaptive layout:
double doors, a front-only sliding door, a portal/transom combination and an
arched door. Their protected entities match exactly and CAD audits find no errors.
Print-window and monochrome JPG behavior pass existing tests.

The full CAD option suite was run twice: once with the correction, once with
`drawing.adapt_order_sheet` disabled. Both runs report **389 PASS / 9 FAIL**.
The nine failure lines match exactly, including details. These are the existing
transom divider/flower, back-frame mirroring, dimension-offset and integrated-door
frame/transom issues; this correction does not repair them.

`git diff --check` passes. Tests use `F:/codex/test-data-fixed-aspect`, not the
business data directory. Existing account-data changes and `.superpowers/` are
excluded from the commit.

## Visual Artifacts and Limits

Artifacts are in `F:/codex/fixed-aspect-verification`:

- `adaptive-0.dxf` through `adaptive-3.dxf`: corrected real CAD documents.
- `before-0.jpg` / `after-0.jpg` through four comparison pairs.
- `cad-options.log` and `cad-baseline.log`: complete option regression outputs.

The inspected layouts retain the landscape template ratio, leave notes inside
the upper left-panel region and keep table/footer text clear of the drawings.
Notes are visibly larger than in the prior correction. Front-only views retain
horizontal whitespace when the frame ratio and unscaled door cannot fill both
axes. Short notes may also leave whitespace once either their width or height
limits further uniform enlargement; text is never distorted to force coverage.

JPG samples use the existing ezdxf/matplotlib renderer for layout verification.
They are **not native AutoCAD plot verification**. Native AutoCAD printing has
not been retested. No paid image-generation requests were made.
