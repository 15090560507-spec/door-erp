import { Plus, Trash2 } from "lucide-react";
import { salesOrderChargeAmount } from "@/lib/salesOrderPricing";
import type { SalesOrderChargeLine, SalesOrderEditorLine } from "@/lib/salesOrderTypes";

const itemTypes = ["主门", "门套", "门框", "五金", "运输", "安装", "其他"];

function money(value: number) {
  return Number(value || 0).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function OrderChargeEditor({ lines, charges, disabled, onAdd, onChange, onRemove }: {
  lines: SalesOrderEditorLine[];
  charges: SalesOrderChargeLine[];
  disabled: boolean;
  onAdd: () => void;
  onChange: (index: number, changes: Partial<SalesOrderChargeLine>) => void;
  onRemove: (index: number) => void;
}) {
  const total = charges.reduce((sum, item) => sum + salesOrderChargeAmount(item), 0);
  return (
    <section className="order-editor__section">
      <div className="order-editor__section-title">
        <div><h3>价格明细</h3><p>门、门套、门框和五金可以合并报价，也可以拆成独立项目。</p></div>
        <div className="order-charge-heading"><strong>¥{money(total)}</strong><button type="button" className="ui-button ui-button--secondary" disabled={disabled} onClick={onAdd}><Plus size={15} />添加项目</button></div>
      </div>
      <div className="order-charge-list">
        {charges.map((charge, index) => (
          <article className="order-charge-row" key={charge.id || `${charge.door_line_no}-${index}`}>
            <label><span>关联门樘</span><select disabled={disabled} value={charge.door_line_no || ""} onChange={(event) => onChange(index, { door_line_no: event.target.value ? Number(event.target.value) : null })}><option value="">整单项目</option>{lines.map((line, lineIndex) => <option key={line.task_id} value={lineIndex + 1}>{lineIndex + 1}. {line.product_name || line.door_type || "未命名门"}</option>)}</select></label>
            <label><span>项目类型</span><select disabled={disabled} value={charge.item_type} onChange={(event) => onChange(index, { item_type: event.target.value })}>{itemTypes.map((type) => <option key={type}>{type}</option>)}</select></label>
            <label className="order-charge-row__name"><span>品名</span><input disabled={disabled} value={charge.product_name} onChange={(event) => onChange(index, { product_name: event.target.value, source_type: "manual" })} /></label>
            <label><span>规格</span><input disabled={disabled} value={charge.specification} onChange={(event) => onChange(index, { specification: event.target.value, source_type: "manual" })} /></label>
            <label><span>数量</span><input disabled={disabled} type="number" min="0" step="0.001" value={charge.quantity || ""} onChange={(event) => onChange(index, { quantity: Number(event.target.value) || 0 })} /></label>
            <label><span>单位</span><input disabled={disabled} value={charge.unit} onChange={(event) => onChange(index, { unit: event.target.value })} /></label>
            <label><span>单价</span><input disabled={disabled} type="number" min="0" step="0.01" value={charge.unit_price || ""} onChange={(event) => onChange(index, { unit_price: Number(event.target.value) || 0 })} /></label>
            <div className="order-charge-row__amount"><span>金额</span><strong>¥{money(salesOrderChargeAmount(charge))}</strong></div>
            <button type="button" className="order-charge-row__remove" disabled={disabled} onClick={() => onRemove(index)} title="删除价格项目" aria-label={`删除第${index + 1}条价格项目`}><Trash2 size={16} /></button>
          </article>
        ))}
        {!charges.length && <div className="order-charge-empty">还没有价格项目，请从报价带入或手工添加。</div>}
      </div>
    </section>
  );
}
