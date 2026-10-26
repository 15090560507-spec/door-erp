# Glass Pattern Controls Verification

## Delivered Rules

- Vertical B2/B4 bars draw no added perimeter, miter corner joins, or glass hatch. Their spacing controls bar pitch; glass inset is hidden and has no effect.
- Six/eight-grid internal spacing controls each paired-line gap. The user explicitly confirmed preserving grid count and equally divided center positions.
- Double-border, flower, and corner-return internal spacing remains connected to its existing inner pattern geometry. Invalid geometry produces a specific range error instead of silently capping the input.
- Front/child inset zero is preserved. Historical back zero-as-inheritance semantics are unchanged.
- Only applicable controls appear. H+ labels identify B2/B4 scope; the shared parameter keys are unchanged. Single perimeters expose inset, not a nonexistent internal-line control.
- The displayed label is `单圈外围线（玻璃）`; persisted values remain `单圈外围线`. The closed variant is unchanged.
- Form layout, account data, templates, and the earlier three metadata inputs are not changed by this repair.

## Automated Checks

- 60 Python unittest tests passed: new pattern geometry tests plus drawing-input metadata, CAD download, order layout, sheet branding, and disc patterns.
- New geometry tests cover all six internal-line patterns, no added bar hatch/perimeter, zero inset, explicit range errors, exact grid gaps/counts/centers, front/back independence, and child/mother independence.
- 23 Node tests passed, including five new applicability/display-label tests and existing API, area, money, quotation layout, and inventory tests.
- TypeScript `tsc --noEmit --incremental false` passed.
- Targeted ESLint: zero errors, two existing unused-variable warnings in DoorForm (`MATERIALS`, `readOnly`).
- `git diff --check` passed.

## Browser Checks

Chrome/Playwright used the isolated local data service at 8164 and the existing-layout frontend at 3164. Checked six internal-line options, display-only renaming, perimeter control visibility, mixed B2/B4 applicability, and independent inputs for all four face/child groups. Desktop 1600px and mobile 390px screenshots were inspected. No page errors or horizontal mobile overflow.

Local artifacts: `F:/codex/glass-pattern-controls-verification/` (screenshots and `report.json`). No production data or paid image-generation calls were used.

## Existing Regression Failures

The targeted legacy `test_rectangular_glass_line_templates` and vertical-spacing checks produced 38 PASS / 4 FAIL. Running the original committed generator with its original committed rectangular-glass tests in memory produced the same four failing checks (32 PASS / 4 FAIL): transom horizontal divider detection, differing front/back center gaps, flower Y-position grouping, and flower scale grouping. These remain outside this repair. The new grid geometry checks pass independently and assert configured gaps and fixed centers directly; no legacy assertions were removed to hide failures.

No Tencent Cloud deployment was performed.
