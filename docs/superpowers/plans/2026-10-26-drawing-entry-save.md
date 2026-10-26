# Drawing Entry Save and Shared Actions

**Goal:** Keep drawing entry on the same form after saving, update the same task on subsequent saves, and offer identical drawing/quote actions in entry and editing.

**Scope:** Retain DoorForm fields and layout. Share a five-button action bar and render result. Do not change CAD geometry, quote formulas, or review status transitions.

## Implementation
- [x] Add a shared action bar for preview, DXF, rendering, save, and quote.
- [x] Track the saved entry task independently from the task-detail route; deduplicate in-flight saves and preserve the captured form snapshot.
- [x] Reuse the saved task for quote and rendering, including save-before-render. Extend leave protection to entry forms and reset identity only when starting/clearing a new form.
- [x] Extend mocked browser coverage for save/stay, repeated save, reference preservation, exact-task quotation, clear/new identity, failed-save retry, and matching actions across entry/editing.
- [x] Run type checks, targeted lint and regression tests.
- [ ] Commit, push, and provide guarded Tencent Cloud commands.
