# H Panel Pattern Controls

Keep the current form layout and H/H+ structural geometry. Correct the shared B2/B4 decoration path, including independent front/back and child groups.

## Approved Corrections

- Vertical bars are not glass: draw only vertical lines across the B2/B4 region, without glass hatch, added rectangular border, or diagonal corner joins. Glass inset must not affect them.
- Display `单圈外围线（玻璃）` while retaining the stored value `单圈外围线`. The closed variant remains unfilled. Historical values and ordinary door settings must remain compatible.
- A front/child inset of zero must stay zero. Retain the existing back-group zero-as-inheritance convention rather than silently changing historical back settings.
- Every pattern with internal lines must respond to its internal-spacing input, including six/eight-grid patterns. Do not keep ineffective controls visible.
- Out-of-range inputs must fail with a descriptive geometry error rather than silently saturating to a cap.

## Spacing Interpretation

The user confirmed that six/eight-grid spacing controls each paired-line gap, preserving counts and equally divided center positions. Existing double-border, flower, and return patterns retain their existing spacing meaning; vertical bars use bar pitch.

A single perimeter has no internal lines; show its inset but not a misleading internal-spacing control. No-lines shows neither. Vertical-only regions show a non-glass bar-spacing label and no glass-inset input. In mixed H+ regions, labels identify exactly which B2/B4 regions use each control.

## Verification

Compare real DXF geometry at two valid spacing values for every internal-line pattern. Assert no additional glass hatch/perimeter for bars; preserve H structural lines. Cover zero inset, range errors, fixed grid centers/counts under the conservative interpretation, face/child independence, mixed B2/B4 UI applicability, display-only renaming, and desktop/mobile presentation. Exclude account data, template assets, previous metadata input changes, and the DXF transport implementation from this patch.
