# Direct Line-Art Paste Repair

**Goal:** Make the user's usual front-line-art screenshot workflow visible and reliably pasteable.

**Design:** Default to direct front line art, retaining full order-sheet, DXF, and linked-task alternatives. A focusable, non-file-picker upload surface receives Ctrl+V through the source section. An explicit image-picker button opens the file dialog. Ignore text inputs and non-image paste, stop duplicate handling, and show immediate preview/receipt feedback. Full sheets are extracted only when their source mode is selected. No generation/provider call occurs merely from pasting a direct screenshot.

**Cause found:** The page defaulted to linked tasks; the direct upload surface was not mounted until selected. Its paste handler was attached to a label whose click opens the file picker, making focus/paste hard to discover. The reference-workspace paste handler intentionally does not handle source drawings.

- [x] Confirm typical input is front line-art screenshots, inspect source selection and paste handlers.
- [x] Repair default, source-area paste routing and explicit upload controls; keep order-sheet compatibility.
- [x] Verify direct paste preview/no extraction, order-sheet single extraction, text/reference independence, clear/replace, quick-generation payload and mobile layout.
- [ ] Push verified changes and deliver Tencent Cloud commands.

## Verification

- TypeScript no-emit check passed; targeted lint has no errors and the same eight image-element warnings.
- 28 Node regression tests passed.
- Mocked Chrome browser workflow passed: direct mode visible by default; clicking the focus surface does not launch a file picker; image paste previews immediately, makes no extraction request, and creates no reference asset. Clear and explicit file-picker selection work. Two separate order-sheet paste events make exactly two extraction requests, including a child-label paste. Source-area paste replaces direct input, quick requests retain front-side metadata, and reference uploads/history/PSD download remain unaffected.
- Desktop 1600px and mobile 390px source screenshots inspected; no horizontal mobile overflow or page errors. Artifacts: `F:/codex/direct-lineart-paste-verification/`.
- Browser tests dispatch ClipboardEvents without overwriting the user's system clipboard; no paid provider calls were made. No Tencent Cloud deployment was executed.
