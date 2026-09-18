import type { SalesOrderLine } from "@/lib/salesOrderTypes";
import { ORDER_LINE_TECHNICAL_FIELDS } from "./orderLineFields";

function nonempty(record: Record<string, unknown>, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && String(value).trim()) return String(value);
  }
  return undefined;
}

function dimension(value: unknown, fallback: unknown): string {
  const primary = Number(value);
  if (Number.isFinite(primary) && primary > 0) return String(primary);
  const snapshot = Number(fallback);
  return Number.isFinite(snapshot) && snapshot > 0 ? String(snapshot) : "-";
}

function legacyLock(params: Record<string, unknown>): string | undefined {
  const lockBody = String(params.st_val || "");
  if (params.fingerprint_lock) return lockBody ? `指纹锁 / ${lockBody}` : "指纹锁";
  return lockBody || undefined;
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
  const snapshotFacts = [
    { label: "反面款式", value: nonempty(params, ["fmks"]) },
    { label: "门框工艺", value: nonempty(params, ["frame_process"]) },
    { label: "玻璃规格", value: nonempty(params, ["glass_spec"]) },
  ].filter((item): item is { label: string; value: string } => Boolean(item.value));

  return (
    <div className="order-line-details">
      <p>{product} / {doorType} · {dimension(line.width, params.dw)} × {dimension(line.height, params.dh)} mm · {opening} · {color}</p>
      <div className="order-summary-line__technical">
        {ORDER_LINE_TECHNICAL_FIELDS.map((field) => (
          <span key={field.key}>
            {field.label}
            <strong>
              {(field.key === "lock_type"
                ? nonempty(details, ["lock_type"]) || nonempty(topLevel, ["lock_type"]) || legacyLock(params)
                : nonempty(details, field.fallbackKeys)
                  || nonempty(topLevel, field.fallbackKeys)
                  || nonempty(params, field.fallbackKeys))
                || "-"}
            </strong>
          </span>
        ))}
      </div>
      {snapshotFacts.length > 0 && (
        <div className="order-line-details__snapshot">
          <span className="order-line-details__snapshot-title">图纸快照补充</span>
          <dl>
            {snapshotFacts.map((fact) => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}
          </dl>
        </div>
      )}
    </div>
  );
}
