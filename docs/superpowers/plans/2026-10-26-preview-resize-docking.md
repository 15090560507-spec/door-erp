# Preview Resize and Scroll Docking

**Approved behavior:** Default floating size is 1.5 times the previous window (510px width, up to 480px drawing height); default view is front. Support plus/minus sizing and corner resize. Scrolling past the save action bar docks the preview into a large region immediately beneath it; scrolling back restores the previous floating position and size.

## Tasks
- [x] Add bounded default dimensions and resize math; preserve pointer/keyboard movement.
- [x] Share manual/automatic SVG state and controlled side selection so docking does not regenerate or lose the selected view.
- [x] Put one docking home directly beneath the action bar and use frame-throttled scroll observation with no layout oscillation.
- [x] Test size defaults, resizing, front default, drag/touch, docking/restoration, no duplicate requests and existing save/quote/auto-preview behavior.
- [ ] Commit, push and provide front-end-only Tencent Cloud update commands.
