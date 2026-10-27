import { orderLineValue } from "@/lib/salesOrderDisplay";
import type { SalesOrderLine } from "@/lib/salesOrderTypes";
import { ORDER_LINE_TECHNICAL_FIELDS } from "./orderLineFields";

export default function OrderLineDetails({ line }: { line: SalesOrderLine }) {
  const params = line.drawing_snapshot?.params || {};
  const lockBody = String(params.st_val || "");
  const legacyLock = params.fingerprint_lock ? (lockBody ? `指纹锁 / ${lockBody}` : "指纹锁") : lockBody;
  const fields = [
    ...ORDER_LINE_TECHNICAL_FIELDS.filter(field => field.key !== "item_remark").map(field => ({
      label: field.label,
      value: field.key === "lock_type"
        ? orderLineValue(line, ["lock_type"]) || legacyLock
        : orderLineValue(line, field.fallbackKeys),
    })),
    { label: "反面款式", value: orderLineValue(line, ["reverse_door_style", "fmks"]) },
    { label: "门框工艺", value: orderLineValue(line, ["frame_process"]) },
    { label: "玻璃规格", value: orderLineValue(line, ["glass_spec"]) },
  ].filter(field => Boolean(field.value));
  const remark = orderLineValue(line, ["item_remark"]) || line.remark;
  return <div className="order-line-details">
    {fields.length ? <dl className="order-summary-line__technical">{fields.map(field => <div key={field.label}>
      <dt>{field.label}</dt><dd>{field.value}</dd>
    </div>)}</dl> : <p className="order-summary__muted">暂无技术参数</p>}
    {remark && <div className="order-line-details__remark"><span>商品备注</span><p>{remark}</p></div>}
  </div>;
}
