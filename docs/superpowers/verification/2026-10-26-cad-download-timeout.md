# DXF Download Timeout Verification

Date: 2026-10-26. Workspace: `F:/Vibe Coding/door-erp-main - 26.5.28`.

## Repair

- Return materialized editable DXF bytes through Response instead of StreamingResponse(BytesIO(...)).
- Automatically include Content-Length, retaining filename encoding, cache/layout headers, media type, and exact bytes.
- Give generateCad a CAD-specific ECONNABORTED message without changing its 60000ms timeout, network errors, server error details, or other endpoints.
- No template, geometry, dimensions, flower, sheet conversion, nginx, production data, or form layout changes.

## Regression Results

The new tests failed before implementation: the old backend lacked Content-Length and a materialized response body; the old frontend used the network-diagnosis timeout message.

After implementation:

- Python unittest: **44 passed** across `test_cad_download`, `test_cad_order_layout`, `test_cad_sheet_branding`, and `test_disc_panel`.
- Pytest: **4 passed** across `test_cad_line_art_ratio.py` and `test_cad_sheet_jpg.py`.
- Selected legacy CAD checks: **16 PASS / 0 FAIL** for SVG preview, flat thresholds, and product-style/panel-geometry isolation. The script's failure counter was asserted explicitly; these are checks rather than unittest test cases.
- Node: **18 passed**, including five new API tests and all existing frontend lib tests.
- `tsc --noEmit --incremental false`: passed.
- ESLint on `src/lib/api.ts` and `src/lib/api.test.ts`: passed.
- `git diff --check`: passed.

Tests used `F:/codex/test-data-cad-timeout-fix`, not production DATA_DIR. The first supplementary JPG run found matplotlib missing from the project virtual environment; rerunning with the existing `F:/codex/door-erp-test-deps` appended to sys.path passed all four tests. No packages were installed or dependency files changed. Existing FastAPI/Starlette deprecation and Node package-type warnings remain outside this repair.

## Real DXF Response Measurement

Sample: four-leaf door, 2440 x 2520mm, generated using the current template.

| Measurement | Result |
| --- | --- |
| Editable DXF length | 2,412,373 bytes |
| Newline count | 319,726 |
| Generation plus editable conversion | 0.980231s |
| Former ASGI response body messages | 319,727 |
| Former ASGI body iteration time | 22.520415s |
| Repaired ASGI response body messages | 1 |
| Repaired ASGI body handling time | 0.000907s |
| Cached in-process HTTP request | 0.111490s |
| Content-Length | 2412373 |

Both responses produced identical bytes and SHA-256:

```text
143f8b299252eb885d84998e09339875c61e7a63117bad108003523f7efd8e89
```

The in-process HTTP request also returned identical bytes and HIT on both CAD and editable-download caches. The raw measurement report is `F:/codex/cad-download-timeout-verification/report.json`.

These are local body-processing and in-process HTTP measurements, not TCP packet counts or Tencent cloud download timings. The change removes per-line thread scheduling; it does not promise sub-millisecond network downloads.

## Review And Remaining Verification

The retained editable-sheet regressions cover attribute values, hidden attributes, nested sheets, inherited display, transformations, preserved non-sheet dimensions/hardware, cache separation, and preview/print source isolation. Failed conversion still returns the original error rather than partial DXF output. A fixed test clock makes the filename assertion deterministic.

The complete legacy CAD baseline and a production Next build were not rerun for this narrow transport change. No browser layout changed. The cloud site has not been deployed or live-tested from this session. After rebuilding backend and frontend, verify the same formerly failing door downloads fully before the 60-second limit and opens normally in CAD. Keep layout/new-field work deferred until this repair is confirmed online.

## Delivery

Code and tests were committed as `02b4b5f` and pushed successfully to `15090560507-spec/door-erp`, branch `feat/semicircle-handles-and-quote-form-improvements`. A final focused route rerun passed all four tests after fixing the test clock. Delivery-status updates are documentation-only. The existing user database modification and unrelated untracked assets were not staged or committed. Tencent cloud deployment remains outstanding.
