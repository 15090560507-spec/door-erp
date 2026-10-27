import type { SalesOrderLine } from "./salesOrderTypes";

function nonempty(record: Record<string, unknown> | undefined, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    const value = record?.[key];
    if (value !== undefined && value !== null && String(value).trim()) return String(value);
  }
  return undefined;
}

export function orderLineValue(line: SalesOrderLine, keys: readonly string[]): string | undefined {
  return nonempty(line.technical_details as unknown as Record<string, unknown>, keys)
    || nonempty(line as unknown as Record<string, unknown>, keys)
    || nonempty(line.drawing_snapshot?.params, keys);
}

function dimension(primary: unknown, fallback: unknown) {
  const value = Number(primary);
  if (Number.isFinite(value) && value > 0) return String(value);
  const snapshot = Number(fallback);
  return Number.isFinite(snapshot) && snapshot > 0 ? String(snapshot) : "-";
}

export function orderLineOverview(line: SalesOrderLine) {
  const params = line.drawing_snapshot?.params || {};
  return {
    product: orderLineValue(line, ["product_name"]) || "未填写产品",
    doorType: orderLineValue(line, ["door_type"]) || "未填写门型",
    dimensions: `${dimension(line.width, params.dw)} × ${dimension(line.height, params.dh)} mm`,
    opening: orderLineValue(line, ["opening_direction"])
      || [nonempty(params, ["sel_kx"]), nonempty(params, ["sel_nk"])].filter(Boolean).join("") || "未填写开向",
    color: orderLineValue(line, ["color", "ys"]) || "未填写颜色",
  };
}
