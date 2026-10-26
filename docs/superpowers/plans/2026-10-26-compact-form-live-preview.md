# Compact Form and Optional Live Preview

**Approved scope:** Move quote image recognition below the quotation preview; rebalance the shared drawing form into three columns with panel settings always expanded. Add a right-side preview dock with an automatic-update switch, off by default.

## Design
- Columns: order/material/hardware; structure/dimensions/frame/gaps; panel/trim/notes/occlusion. Keep parameter meanings, saved data, calculations and review flow unchanged.
- A wide viewport reserves a sticky right preview dock; narrower screens show a compact in-flow dock, avoiding covered inputs.
- Automatic preview waits 1500 ms after geometry changes. Requests are serialized and intermediate pending inputs replaced by the newest input. Stale responses do not replace the latest drawing. Keep the last successful SVG during loading/errors; cache up to eight snapshots locally.
- No AI calls or auto-save. Partial forms can preview once the backend's geometry-required fields are present; missing commercial fields do not block the dock. Invalid/incomplete geometry shows an inline status, never repeated modal errors.
- Quote image recognition is only relocated, not removed or invoked automatically.

## Tasks
- [x] Reorganize the shared form and quote recognition placement.
- [x] Implement bounded latest-only preview queue and dock with explicit auto opt-in.
- [x] Verify debounce, serialization, stale suppression, disabling, cache reuse, failure retention, cross-record isolation and responsive layouts.
- [ ] Run regression checks, commit, push and provide guarded Tencent Cloud update commands.
