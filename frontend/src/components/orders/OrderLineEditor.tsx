import { AlertTriangle, FileCheck2, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import StatusChip from "@/components/workspace/StatusChip";
import type { SalesOrderEditorLine } from "@/lib/salesOrderTypes";

function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return <label className="order-field"><span>{label}{required && <b>*</b>}</span>{children}</label>;
}

export default function OrderLineEditor({ line, index, disabled, onChange, onRemove }: { line: SalesOrderEditorLine; index: number; disabled: boolean; onChange: (changes: Partial<SalesOrderEditorLine>) => void; onRemove: () => void }) {
  const quoteValue = line.quote_id ? `${line.quote_id}:${line.quote_group_index ?? 0}` : "";
  const warnings = [line.source_type === "drawing" && !line.quote_id ? "请选择对应报价" : "", line.source_changed ? "图纸版本已变化，保存草稿后再确认" : "", line.width <= 0 || line.height <= 0 ? "宽、高必须大于 0" : "", line.quantity <= 0 ? "数量必须大于 0" : "", line.unit_price <= 0 ? "单价必须大于 0" : ""].filter(Boolean);
  return (
    <article className={`order-line-editor${warnings.length ? " has-warning" : ""}`}>
      <header className="order-line-editor__header"><div className="min-w-0"><div className="order-line-editor__title"><strong>{index + 1}. {line.product_name || line.door_type || "未填写产品"}</strong><StatusChip tone={line.source_type === "drawing" ? "green" : "neutral"}>{line.source_type === "drawing" ? "终审图纸" : "手工录入"}</StatusChip>{line.source_type === "drawing" && <StatusChip tone={line.quote_id ? "blue" : "amber"}>{line.quote_id ? `报价 #${line.quote_id}` : "缺报价"}</StatusChip>}</div><p>{line.source_type === "drawing" ? `图纸 ${line.task_id} · 技术版本 ${line.drawing_revision || line.source_approved_at || "待保存"}` : "特殊订单业务明细"}</p></div>{!disabled && <button type="button" className="order-line-editor__remove" onClick={onRemove} title="移除明细" aria-label={`移除第${index + 1}项`}><Trash2 size={16} /></button>}</header>
      {line.source_type === "drawing" ? <div className="order-line-editor__snapshot"><FileCheck2 size={18} aria-hidden="true" /><dl><div><dt>产品 / 门型</dt><dd>{line.product_name || "-"} / {line.door_type || "-"}</dd></div><div><dt>规格</dt><dd>{line.width} × {line.height} mm</dd></div><div><dt>开向 / 颜色</dt><dd>{line.opening_direction || "-"} / {line.color || "-"}</dd></div><div><dt>终审状态</dt><dd>{line.drawing_status || "-"}</dd></div></dl></div> : <div className="order-line-editor__fields order-line-editor__fields--technical"><Field label="产品名称" required><input disabled={disabled} value={line.product_name} onChange={(event) => onChange({ product_name: event.target.value })} /></Field><Field label="门型"><input disabled={disabled} value={line.door_type} onChange={(event) => onChange({ door_type: event.target.value })} /></Field><Field label="宽(mm)" required><input disabled={disabled} type="number" min="0" value={line.width || ""} onChange={(event) => onChange({ width: Number(event.target.value) || 0 })} /></Field><Field label="高(mm)" required><input disabled={disabled} type="number" min="0" value={line.height || ""} onChange={(event) => onChange({ height: Number(event.target.value) || 0 })} /></Field><Field label="开向"><input disabled={disabled} value={line.opening_direction} onChange={(event) => onChange({ opening_direction: event.target.value })} /></Field><Field label="颜色"><input disabled={disabled} value={line.color} onChange={(event) => onChange({ color: event.target.value })} /></Field></div>}
      <div className="order-line-editor__fields order-line-editor__fields--business">
        {line.source_type === "drawing" ? (
          <Field label="关联报价" required>
            <select
              disabled={disabled}
              value={quoteValue}
              onChange={(event) => {
                const choice = line.quoteChoices.find((item) => `${item.quote_id}:${item.group_index}` === event.target.value);
                onChange({ quote_id: choice?.quote_id || null, quote_group_index: choice?.group_index ?? null, unit_price: choice?.amount || 0 });
              }}
            >
              <option value="">请选择报价</option>
              {line.quoteChoices.map((choice) => (
                <option key={`${choice.quote_id}-${choice.group_index}`} value={`${choice.quote_id}:${choice.group_index}`}>
                  #{choice.quote_id} · {choice.group_name || `第${choice.group_index + 1}组`} · {choice.quote_date || "未填日期"} · ¥{choice.amount.toLocaleString()}
                </option>
              ))}
            </select>
          </Field>
        ) : (
          <Field label="单位"><input disabled={disabled} value={line.unit} onChange={(event) => onChange({ unit: event.target.value })} /></Field>
        )}
        <Field label="数量" required><input disabled={disabled} type="number" min="1" value={line.quantity} onChange={(event) => onChange({ quantity: Math.max(1, Number(event.target.value) || 1) })} /></Field>
        <Field label="单价" required><input disabled={disabled} type="number" min="0" value={line.unit_price || ""} onChange={(event) => onChange({ unit_price: Math.max(0, Number(event.target.value) || 0) })} /></Field>
        <Field label="金额"><input readOnly value={`¥${(line.quantity * line.unit_price).toLocaleString()}`} /></Field>
        <Field label="业务备注"><input disabled={disabled} value={line.remark} onChange={(event) => onChange({ remark: event.target.value })} /></Field>
      </div>
      {warnings.length > 0 && <div className="order-line-editor__warning"><AlertTriangle size={15} />{warnings.join("；")}</div>}
    </article>
  );
}
