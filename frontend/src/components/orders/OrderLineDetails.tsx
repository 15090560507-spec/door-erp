import type { SalesOrderLine } from "@/lib/salesOrderTypes";
import { ORDER_LINE_TECHNICAL_FIELDS } from "./orderLineFields";

function nonempty(record: Record<string, unknown>, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && String(value).trim()) return String(value);
  }
  return undefined;
}

function dimension(value: number): string {
  return Number.isFinite(value) && value > 0 ? String(value) : "-";
}

export default function OrderLineDetails({ line }: { line: SalesOrderLine }) {
  const details = line.technical_details as unknown as Record<string, unknown>;
  const topLevel = line as unknown as Record<string, unknown>;
  const params = line.drawing_snapshot?.params || {};
  const product = nonempty(topLevel, ["product_name"]) || nonempty(params, ["product_name"]) || "-";
  const doorType = nonempty(topLevel, ["door_type"]) || nonempty(params, ["door_type"]) || "-";
  const opening = nonempty(topLevel, ["opening_direction"]) || nonempty(params, ["opening_direction"])
    || [nonempty(params, ["sel_kx"]), nonempty(params, ["sel_nk"])].filter(Boolean).join("")
    || "-";
  const color = nonempty(topLevel, ["color"]) || nonempty(params, ["color", "ys"]) || "-";

  return (
    <div className="order-line-details">
      <p>{product} / {doorType} · {dimension(line.width)} × {dimension(line.height)} mm · {opening} · {color}</p>
      <div className="order-summary-line__technical">
        {ORDER_LINE_TECHNICAL_FIELDS.map((field) => (
          <span key={field.key}>
            {field.label}
            <strong>
              {nonempty(details, field.fallbackKeys)
                || nonempty(topLevel, field.fallbackKeys)
                || nonempty(params, field.fallbackKeys)
                || "-"}
            </strong>
          </span>
        ))}
      </div>
    </div>
  );
}
