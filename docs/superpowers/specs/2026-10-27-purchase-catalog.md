# Direct Purchasing and Catalog Capture

Approved scope: a top-right New Purchase Order action independent from demand-based merging. Material input accepts searchable existing records or a new name, specification and base unit. Supplier input accepts searchable existing suppliers or a new name.

Saving a draft atomically creates missing supplier, material and supply relationships. Exact name/specification/unit matches reuse active materials; ambiguous or disabled matches require explicit correction, never silent replacement. Existing master metadata is not edited. Canceling the dialog creates nothing; failed saves roll back all changes.

Order confirmation updates only that supplier's supply reference price and appends price history when changed (or first confirmed price). Drafts do not update reference prices. Existing order prices remain snapshots. Orders use material base units; existing supplier purchase-unit conversion is preserved and applied to reference prices. Existing tax metadata is preserved, without adding tax calculations.

Scoped catalog creation is authorized by production.purchase; general masterdata.write remains separately protected. New orders store supplier identity; historical orders without identity keep their previous behavior. Client request keys prevent retry-created duplicate orders and are scoped to the actor.

UI: searchable choices show names/specifications/units; new material fields remain editable. Existing material fields cannot silently edit the master. Suggested supplier prices are editable and never overwrite manually entered prices. Keep existing receipt/inspection workflow unchanged. No new dependencies or destructive migrations.
