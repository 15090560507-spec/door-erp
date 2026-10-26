# DXF Download Timeout Repair

## Approved Scope

The user approved repairing DXF transfer, reporting CAD-specific timeouts, adding regression coverage, and pushing the fix to the existing feature branch. Layout changes and new drawing fields remain deferred.

## Evidence

- The browser cancels CAD downloads after the shared 60-second Axios timeout.
- Supplied October 26 cloud logs show CAD responses beginning with HTTP 200, followed by proxy request completion about 59.9, 58.7, and 59.6 seconds later. HTTP 200 records response headers, not proof of a fully received file.
- The download handler finishes drawing and editable-sheet conversion before constructing its response. It passes BytesIO to StreamingResponse, which iterates DXF lines through the thread pool.
- A local 2,168,607-byte sample contains 250,384 lines. Iterating the existing response took 17.018 seconds without HTTP transport; a single-payload iterator took less than one millisecond. These are local measurements, not cloud timings.
- The newer template increases the line count even for ordinary doors. This amplifies a pre-existing transfer inefficiency; it does not prove every cloud delay has the same cause.

## Design

Return the already-materialized editable DXF bytes through FastAPI Response. This provides Content-Length and a single ASGI body message instead of per-line synchronous iteration. Preserve the binary media type, encoded download filename, cache indicators, layout warnings, and response bytes exactly. The transport may split the body into packets; a single ASGI message does not imply a single TCP packet.

When generateCad encounters Axios ECONNABORTED, report `DXF 文件生成或下载超时，请稍后重试` instead of attributing it to network failure. Keep the 60-second timeout, network-error handling, server-error details, preview, JPG export, and other endpoints unchanged.

## Non-Goals

- No changes to template assets, dimensions, flower blocks, sheet bursting, rendering, or production data.
- No nginx buffering changes, generic timeout increases, job queues, or deployment through this session.

## Verification And Delivery

Add deterministic tests for a newline-heavy payload, Content-Length, byte identity, one ASGI body message, filenames, and cache/layout headers. Retain editable-sheet geometry, attributes, and untouched preview/print source tests. Test timeout copy independently from network and server errors, and verify successful Blob handling. Run focused CAD regressions, frontend type checking, and lint on touched TypeScript. Commit only the approved files and push the existing branch. Tencent cloud verification follows deployment by the user; do not claim the live site is fixed before that.
