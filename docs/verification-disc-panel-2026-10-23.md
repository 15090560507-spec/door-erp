# Disc Panel Verification

## Workspace

Implemented only in `F:/Vibe Coding/door-erp-main - 26.5.28` after fast-forwarding its branch from `8f48118` to `9a5b3e3`. Original local files were backed up to `F:/codex/main-sync-backup-20261023-092542`. The supplied template DXF contains all four required blocks and is included in delivery without rewriting it. Account data and unrelated local files are excluded.

## Behavior

- Circle, circular peony, and four-leaf peony subtypes under the existing disc panel style, separately configurable for all four panel groups.
- The actual YXMDHZ/YXMDHY and SBMDHZ/SBMDHY blocks are selected by lock-to-hinge direction. Their zero base point is anchored on the lock edge. Radius 700 gives scale 0.7; radius 1000 gives scale 1, independently of the supplied block's slightly asymmetric extents.
- Existing radius default 120 and circle subtype remain for old records. First choosing a flower from the untouched circle default selects 700mm. Existing nondefault radii are preserved.
- Nullable height means follow the current face's existing handle-placement rule; explicit height is independent. Ordinary template handles use panel bottom +1000; circular/sized handles use 1200; absent or groove handles fall back to 1050. Handle geometry itself is not changed.
- Nullable exterior fill selects empty for circle and vertical stripes for flowers. Explicit empty fill remains empty after saving and reopening.
- Actual outer arcs/closed bulged contours are flattened for exclusion. The existing ezdxf hatch renderer generates pattern lines; the concave clipper identifies interior intervals and only their complement is emitted. This avoids touching-boundary hatch/island ambiguities and does not depend on WIPEOUT.
- Invalid sizes or out-of-panel flower extents produce errors instead of silently disappearing or shrinking. Missing blocks produce explicit errors rather than placeholder rectangles.

## Checks

- Backend tests initially failed because `disc_panel` did not exist. A later integration check caught the hatch/island boundary issue; exact per-line clipping corrected it.
- Focused regression: **57 tests and 41 subtests passed** across disc, branding, layout, editable DXF, JPG, line-art, ratio, and multi-door quote suites.
- Disc tests cover real block names, 0.7/1 scaling, both lock directions, null/explicit fill, height resolution, invalid/missing inputs, actual front/back generation, independent child/back styles and manual heights, circle/handle linkage, and five interior samples per fill segment against each flower exclusion.
- TypeScript passed. Scoped ESLint has zero errors and only two preexisting DoorForm unused-variable warnings.
- Playwright passed at 1440px and 390px: all four groups, subtype changes, initial flower radius/fill, explicit empty fill, auto reset, independent child radii, save/reload and no workflow status mutation. No page errors.
- Inspected actual printed JPGs of both flowers, the SVG preview, and the mobile controls screenshot. Artifacts are in `F:/codex/disc-panel-verification` (DXF, JPG, SVG, desktop/mobile screenshots).
- Local frontend: `http://127.0.0.1:3133/dashboard`; backend: port 8133. Both run from the main workspace, with isolated test data for the backend. No production data, paid AI generation, or Tencent Cloud deployment used.

## Limits

The full legacy CAD baseline was not rerun; this does not claim to fix its known unrelated failures. The actual CAD geometry and existing server renderer were checked, not an AutoCAD desktop plotting session. Existing exported files must be regenerated to show the new styles.
