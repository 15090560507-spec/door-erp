# Reference Pattern Verification

## Delivered Scope

- B2 reference entry for front, back and child panels; rectangular glass transom entry.
- Explicit image recognition using the quotation AI connection, with a separate prompt and parser. No AI calls on parameter edits, preview refresh, saved-task reload or template selection.
- Paste, drop, upload, rectangular crop, source/vector comparison, real millimetre line width, inset, fixed edge-detail zones, mirror and point correction.
- Reviewed geometry is embedded in the drawing in both apply modes. Personal template creation is optional and explicit.
- Durable SQLite jobs, actor-scoped submission deduplication, bounded worker concurrency and result recovery after the dialog closes. Save the form to preserve its pending-job pointer across reloads.
- Deterministic CAD contours from validated orthogonal centerlines; actual DXF generation uses those contours, not a preview bitmap.

## Verification

- Backend: 54 tests passed across reference patterns, glass controls, input options, management security, disc panels and CAD preview views.
- Frontend: 59 library tests passed; TypeScript `tsc --noEmit` passed.
- Targeted ESLint: zero errors; existing unused `MATERIALS` warning in DoorForm remains unchanged.
- Browser: desktop 1600x1100 and mobile 390x900 passed. Covered crop, Ctrl+V, pending job save/reload/recovery, manual geometry preservation, optional template saving, invalid-size rejection and real DXF export. No horizontal dialog overflow or browser errors.
- Browser recognition/connection/template responses were mocked; task persistence, contour preview and DXF generation used the real isolated local backend. The server-side background worker and model HTTP payload were separately tested with mocked inference/transport.
- Local artifacts: `F:/codex/reference-pattern-browser/desktop-b2.png`, `mobile-b2.png`, `reference-b2-and-transom.dxf`.

## Limitations and Operations

- No real paid model inference was performed. Recognition accuracy, model compatibility, latency and cost require a trial with the configured visual model. No accuracy or response-time guarantee is inferred from mocked tests.
- First version supports horizontal/vertical motifs and rectangular glass transoms, not arbitrary curves, diagonal motifs or arched clipping. Model output is untrusted, validated and requires user review before application.
- Trial dimensions in the review dialog are editable sample dimensions, not automatically extracted B2 dimensions. CAD validates the actual target region and rejects insufficient space or overlapping parallel bands.
- Recognition uses an OpenAI-compatible chat-completions endpoint with image input and JSON output. A text-only quotation model is insufficient. Provider failures are surfaced; no automatic paid retry occurs.
- Deployment currently uses one backend worker. Startup marks interrupted jobs failed rather than automatically charging again. Multiple backend processes would require worker leases or an external queue before scaling.
- New storage: `DATA_DIR/reference_patterns.db`, including source images, jobs and personal templates. Include this database in the existing consistent data-backup workflow. Template ownership is private; drawing-role access to task-linked source/job IDs follows the application's shared drawing access model.
- Rebuild both backend and frontend; backend adds Shapely. Existing task data and built-in style defaults remain compatible. No production Next.js build or Tencent deployment was performed during local verification.
