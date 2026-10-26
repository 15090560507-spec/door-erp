# Drawing Preview and Quote Actions

**Goal:** Reveal CAD preview only on request, fit selectable front/back/both views without distortion, unify the drawing toolbar, and offer direct quotation from task rows.

**Design:** Keep CAD download geometry and the existing form unchanged. Add an opt-in grouped door-view SVG to the existing cached preview endpoint; the browser fits the actual SVG group bounds and switches views locally. Retain the legacy SVG renderer for other callers. Quote navigation from a dirty or new form requires explicit save confirmation; task-row quotation opens its exact task ID.

## Tasks
- [x] Add grouped front/back SVG generation and separate cache key with geometry tests.
- [x] Extract responsive preview panel with local side switching, fit-to-content and no extra generation button; hide it before the first request.
- [x] Unify secondary button styles and order preview/DXF/render/quote/save, highlighting only save.
- [x] Add save-before-quote confirmation and task-row quote icon before copy/delete.
- [x] Verify browser interactions, real generated CAD framing, mobile/desktop screenshots, type checks and regression tests.
- [ ] Commit, push the approved GitHub branch and provide Tencent Cloud update commands.
