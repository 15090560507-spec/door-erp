import type { SalesOrderChargeLine } from "@/lib/salesOrderTypes";

export function salesOrderChargeAmount(charge: SalesOrderChargeLine) {
  const amount = Number(charge.quantity || 0) * Number(charge.unit_price || 0);
  return charge.source_type === "quote" ? Math.round(amount) : Math.round(amount * 100) / 100;
}
