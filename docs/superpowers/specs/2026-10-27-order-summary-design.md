# Order Summary Readability

Approved in chat: continuous sections, no tabs. Keep the left order list and the existing order, pricing and receipt business behavior.

## Presentation

The right detail has five clearly labelled sections in order: 订单概况, 门樘明细, 价格明细, 收款信息, 图纸附件. Section titles are 18px, line titles 16px, body 14px, auxiliary text 12px, with zero letter spacing. Use restrained neutral bands, separators and blue accents, not nested cards or new decorative imagery.

The order header retains order number, status and existing actions. Format its update time for reading without changing stored timestamps. Basic facts wrap rather than silently truncate long customer/project/address values.

Door rows show identity at left, door type/dimensions/opening/color in a central summary, and quantity/amount at right. Technical parameters occupy one labelled grid below. Merge reverse style, frame process and glass specification into that grid; remove the separate 图纸快照补充 presentation. Retain frozen drawing_snapshot data. Resolve display values from confirmed technical fields, then confirmed line fields, then its stored snapshot; do not fetch the live drawing to replace confirmed values. Source task/revision move into a closed native details disclosure. Changed-source warnings remain visible.

Charge rows use three columns: product name, specification/usage/unit price, amount. The middle summary is vertically centered. Preserve charge amounts and the existing calculation fallback exactly. Long names and details wrap. No quantity rounding or currency calculation changes.

Receipt plan, actual receipts and totals remain distinct within 收款信息. Keep receipt/reversal/edit/cancel/retry actions and permissions unchanged. Move attachment summary last, render a single empty state for no files, and otherwise show populated categories with existing downloads and errors intact.

## Responsive Behavior and Scope

Use container-aware grids for narrow detail panels, not viewport-scaled fonts. Below compact widths, stack middle summaries under identity while keeping amounts readable; no whole-page horizontal overflow. Keep CSS scoped to the order summary so editor/production layouts do not change. No database or API schema changes.

## Verification

Unit tests cover confirmed/snapshot value precedence, old orders missing details, and rendering snapshot-only values without mutation. Browser fixtures cover long texts, multiple doors/charges, changed sources, manual lines, empty/populated attachments, receipt callbacks and error/retry states. Inspect desktop, 4K and mobile screenshots and actual font sizes/element bounds. Run TypeScript, targeted ESLint and order/receipt backend regressions before scoped GitHub push and Tencent update instructions.
