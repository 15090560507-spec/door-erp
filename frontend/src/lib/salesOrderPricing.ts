import type { SalesOrderChargeLine } from "@/lib/salesOrderTypes";

export function salesOrderChargeAmount(charge: SalesOrderChargeLine) {
  const amount = Number(charge.quantity || 0) * Number(charge.unit_price || 0);
  const doors = Math.max(1, Number(charge.rounding_door_quantity || 1));
  return charge.source_type === "quote" ? Math.round(amount / doors) * doors : Math.round(amount * 100) / 100;
}
