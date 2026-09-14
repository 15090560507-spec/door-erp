import { Banknote, CalendarDays, MapPin, Pencil, ReceiptText, RotateCcw, UserRound, XCircle } from "lucide-react";
import StatusChip, { type StatusTone } from "@/components/workspace/StatusChip";
import { salesOrderChargeAmount } from "@/lib/salesOrderPricing";
import type { SalesOrder, SalesOrderReceipt } from "@/lib/salesOrderTypes";
import ProvisioningStatus from "./ProvisioningStatus";
import { salesOrderStatusLabel } from "./OrderList";

const statusTone: Record<string, StatusTone> = { draft: "blue", confirmed: "green", fulfilling: "blue", completed: "green", cancelled: "neutral" };

function value(params: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const current = params[key];
    if (current !== undefined && current !== null && String(current).trim()) return String(current);
  }
  return "-";
}

export default function OrderSummary({ order, busy, onEdit, onCancel, onRetry, onReceipt, onReverseReceipt }: { order: SalesOrder; busy: boolean; onEdit: () => void; onCancel: () => void; onRetry: () => void; onReceipt: () => void; onReverseReceipt: (receipt: SalesOrderReceipt) => void }) {
  return (
    <article className="order-summary">
      <header className="order-summary__header">
        <div><p className="order-summary__eyebrow">销售订单</p><h2>{order.order_no}</h2><p>版本 {order.version} · 更新于 {order.updated_at || order.order_date}</p></div>
        <div className="order-summary__actions"><StatusChip tone={statusTone[order.status]}>{salesOrderStatusLabel[order.status] || order.status}</StatusChip>{["confirmed", "fulfilling", "completed"].includes(order.status) && <button type="button" className="ui-button ui-button--primary" disabled={busy || order.unpaid_amount <= 0.005} onClick={onReceipt}><Banknote size={15} />登记收款</button>}{order.status === "draft" && <button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={onEdit}><Pencil size={15} />编辑订单</button>}{["draft", "confirmed"].includes(order.status) && <button type="button" className="ui-button ui-button--danger" disabled={busy} onClick={onCancel}><XCircle size={15} />取消</button>}</div>
      </header>
      <ProvisioningStatus order={order} busy={busy} onRetry={onRetry} />
      <section className="order-summary__facts" aria-label="订单基本信息">
        <div><UserRound size={17} /><span>客户</span><strong>{order.customer_name}</strong><small>{order.project_name || "未填写项目"}</small></div>
        <div><CalendarDays size={17} /><span>交期</span><strong>{order.delivery_date || "未设置"}</strong><small>订单日期 {order.order_date}</small></div>
        <div><ReceiptText size={17} /><span>订单金额</span><strong>¥{order.total_amount.toLocaleString()}</strong><small>已收 ¥{order.paid_amount.toLocaleString()} · 未收 ¥{order.unpaid_amount.toLocaleString()}</small></div>
        <div><MapPin size={17} /><span>交付信息</span><strong>{order.salesperson || "未填写销售员"}</strong><small>{order.delivery_address || "未填写收货地址"}</small></div>
      </section>
      <section className="order-summary__section">
        <div className="order-summary__section-title"><div><h3>门樘明细</h3><p>来源图纸、报价和确认快照可逐行追溯。</p></div><strong>{order.lines.length} 项</strong></div>
        <div className="order-summary__lines">{order.lines.map((line) => { const params = line.drawing_snapshot?.params || {}; return <div className={`order-summary-line${line.source_changed ? " has-warning" : ""}`} key={line.id || line.task_id}><div className="order-summary-line__main"><span className="order-summary-line__title"><strong>{line.line_code || `${order.order_no}-${String(line.line_no).padStart(2, "0")}`} · {line.product_name || line.door_type}</strong><StatusChip tone={line.source_type === "manual" ? "neutral" : "green"}>{line.source_type === "manual" ? "手工录入" : "终审图纸"}</StatusChip>{!line.quote_id && line.source_type === "drawing" && <StatusChip tone="amber">缺报价</StatusChip>}</span><p>{line.door_type || "未填门型"} · {line.width} × {line.height} mm · {line.opening_direction || "未填开向"} · {line.color || "未填颜色"}</p><div className="order-summary-line__technical"><span>材质<strong>{value(params, "material", "zzcl")}</strong></span><span>正/反门板<strong>{value(params, "zmks")} / {value(params, "fmks")}</strong></span><span>门框工艺<strong>{value(params, "frame_process")}</strong></span><span>门套<strong>{value(params, "trim_style_outer", "sel_bz")}</strong></span><span>锁具/拉手<strong>{value(params, "fingerprint_lock", "st_val")} / {value(params, "zmls")}</strong></span><span>玻璃<strong>{value(params, "glass_spec")}</strong></span></div><small>{line.source_type === "drawing" ? `图纸 ${line.task_id} · 技术版本 ${line.drawing_revision || "未记录"}` : line.remark || "临时业务明细"}</small>{line.source_changed && <span className="order-summary-line__warning">来源图纸已变化，请取消原订单并重新确认。</span>}</div><div className="order-summary-line__amount"><span>{line.quantity} {line.unit}</span><strong>¥{line.amount.toLocaleString()}</strong></div></div>; })}</div>
      </section>
      <section className="order-summary__section"><div className="order-summary__section-title"><div><h3>价格明细</h3><p>收费项目与门樘技术结构独立，便于门和门套拆分报价。</p></div><strong>{order.charge_lines?.length || 0} 项</strong></div><div className="order-summary__charges">{order.charge_lines?.map((charge) => <div key={charge.id}><span><strong>{charge.product_name}</strong><small>{charge.item_type} · {charge.specification || "无规格"} · {charge.quantity} {charge.unit} × ¥{charge.unit_price.toLocaleString()}</small></span><strong>¥{Number(charge.amount ?? salesOrderChargeAmount(charge)).toLocaleString()}</strong></div>)}</div></section>
      <section className="order-summary__bottom"><div><h3>收款计划</h3>{order.payment_nodes.length ? order.payment_nodes.map((node, index) => <div className="order-summary__payment" key={node.id || index}><span>{node.name}</span><strong>¥{node.due_amount.toLocaleString()}</strong><span>{node.planned_date || "未定日期"}</span><StatusChip tone={node.status === "paid" ? "green" : node.status === "partial" ? "amber" : "neutral"}>{node.status === "paid" ? "已收" : node.status === "partial" ? `已收 ¥${Number(node.paid_amount || 0).toLocaleString()}` : "待收"}</StatusChip></div>) : <p className="order-summary__muted">未配置收款计划</p>}<div className="order-summary__receipts"><div className="order-summary__receipts-title"><h3>实际收款</h3><span>{order.receipts.filter((item) => item.status === "confirmed").length} 笔有效</span></div>{order.receipts.length ? order.receipts.map((receipt) => <div className={`order-summary__receipt${receipt.status === "reversed" ? " is-reversed" : ""}`} key={receipt.id}><span><strong>{receipt.receipt_no}</strong><small>{receipt.receipt_date} · {receipt.payment_method || "未填方式"}{receipt.reference ? ` · ${receipt.reference}` : ""}</small></span><strong>¥{Number(receipt.allocation_amount || 0).toLocaleString()}</strong>{receipt.status === "confirmed" ? <button type="button" title="冲销收款" aria-label={`冲销收款单 ${receipt.receipt_no}`} disabled={busy} onClick={() => onReverseReceipt(receipt)}><RotateCcw size={14}/></button> : <StatusChip tone="neutral">已冲销</StatusChip>}</div>) : <p className="order-summary__muted">尚未登记实际收款</p>}</div></div><div className="order-summary__totals"><p><span>小计</span><strong>¥{order.subtotal.toLocaleString()}</strong></p><p><span>优惠</span><strong>-¥{order.discount_amount.toLocaleString()}</strong></p><p className="is-total"><span>订单总额</span><strong>¥{order.total_amount.toLocaleString()}</strong></p><p className="is-paid"><span>已收</span><strong>¥{order.paid_amount.toLocaleString()}</strong></p><p className="is-unpaid"><span>未收</span><strong>¥{order.unpaid_amount.toLocaleString()}</strong></p></div></section>
    </article>
  );
}
