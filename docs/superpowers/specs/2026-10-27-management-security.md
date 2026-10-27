# Management Authorization and Approval

Approved policy: super administrators and account A retain all business-management permissions. No role/password changes to A. Other accounts use role defaults or an explicit per-account permission set maintained by these business administrators.

Backend permissions cover sales, fulfillment, BOM, purchasing/inventory, workforce and payroll. Unknown management routes deny access. Menu visibility is convenience, not authorization. The server derives permissions from the current user database on each request; client-supplied permissions/approver names are not trusted.

Unpaid shipments require explicit release confirmation, a reason and finance.release. The authorized logged-in operator performs the approval and shipment in the existing transaction; identity, reason and amounts are recorded. This delivery does not introduce a separate two-person application workflow.

Payroll edits/recalculation are allowed only in draft. Submit requires payroll.write; approve/lock/reject require payroll.approve. Reopening approved/locked periods requires payroll.unlock and a nonblank reason, clears approval metadata and requires resubmission. All adjustments and transitions append audit events in the same transaction.

The UI provides account-level permission configuration, removes editable shipment approver names, and disables payroll controls according to permissions and state. Backend checks remain authoritative when pages or requests are tampered with.

Use existing event storage and atomic user JSON writes; preserve historical shipments/payroll. Verify unauthorized calls cause no writes, A retains all permissions, explicit grants/revocations work, frozen wages stay frozen, and fake approver text cannot release debt.
