# Dual Trim Outer-Area Pricing and Drawing Quote Navigation

User confirmed: when both inner and outer trims exist, charge the main door against the larger complete perimeter rectangle (tie: outer), and list the other trim separately at its actual CAD net contour area times the door unit price times a configurable factor (default 0.7). Never combine width from one side with height from the other. Existing lintel ownership stays outer-only when outer trim exists.

Scope is outer-area mode; frame-plus-trim mode and global drawing-area/CAD geometry remain unchanged. Single-trim/no-trim rules and the existing main-door minimum area remain unchanged. Use validated CAD trim metrics for dual-trim dimensions and net area; do not silently omit extra charges if metrics are unavailable.

Persist the factor and explicit generated-row roles. Keep extra-trim price linked to the main unit price despite reordering; allow changing the factor, and derive a new factor from a manually edited extra price when the main price is positive. Historical quotes remain untouched merely by loading them.

Add bottom actions in both new drawing input and existing drawing editors. New drawings are validated/saved before navigation. Existing unsaved edits use the established navigation guard. Quote navigation includes the exact task ID; load its latest existing quotation when available, otherwise prefill a new linked quotation. Do not match by customer names or overwrite unrelated drafts.

Test side selection, tie/single/no trim, non-mixed dimensions, net-area precision/minimums, price links/reorder, factor persistence/validation, unchanged split mode, exact project navigation, new-drawing save, existing unsaved-edit cancellation, and desktop/mobile views. Use isolated test data; do not call paid providers.

Additional user request: keep quotation-preview quantity decimals on one line. Preserve A4/table column widths and exported layout. Use a non-wrapping quantity cell with smaller horizontal padding and measured text fitting for unusually long values; do not round/truncate the stored quantity.
