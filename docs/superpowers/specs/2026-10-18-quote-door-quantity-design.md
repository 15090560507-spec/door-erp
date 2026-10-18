# Quote Door Quantity and Linked Outer Dimensions

Date: 2026-10-18

## Approved Design

The user approved the written proposal and interactive `quote-door-quantity.html`
mockup, then requested implementation. Add `doorQuantity` to each quote group as
a positive integer, default 1 for legacy data. Items always represent one door.
Group total is the existing rounded per-item sum multiplied once by doorQuantity.
Do not change dimensions, accessory unit prices, or per-door minimum-area rules.

The editor shows a quantity stepper in the group header, per-door totals, and the
extended group total. Save/update/history reload, browser preview, Excel and the
shared HTML/JPG/PDF renderer must preserve the same contract. History door counts
sum group quantities rather than count specification groups.

Sales-order quote choices retain a per-door `amount` and per-door items. Expose
`door_quantity` separately, use it when initially selecting a quoted drawing or
changing its quote, and keep existing per-door charge expansion exactly once.
Confirmed orders continue generating independent production doors using existing
order quantity logic. Never retroactively change saved/confirmed orders.

Linked project labels append the calculated outer dimensions after the frame
dimensions when trim/portal/landscape structures produce a different exterior.
Use drawing parameters and the existing dimension resolver, not edited quote rows.
Missing parameters must not display misleading zero dimensions. Retain current
selection/search behavior and show the same label in selected and result states.

Invalid counts (zero, negative, fractional or non-numeric) must not be saved or
silently converted. Preserve legacy groups without a quantity as one door.

## Scope and Verification

This batch changes only quote quantities, their downstream order handoff and
linked dimension labels. It does not address the pending-task-count investigation
or change CAD geometry/area formulas. Tests use isolated databases, no cloud data.

Verify persistence/legacy/validation, per-door arithmetic and order handoff, mixed
group totals, export formulas/HTML, and project dimensions including clear-opening,
transom and landscape cases. Run browser checks on desktop/mobile for quantities,
save/reload and preview totals, then generate actual PDF/JPG/XLSX samples.
Preserve existing unrelated data and automatically push the authorized branch.
