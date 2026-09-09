import { CalendarDays, MapPin, Pencil, ReceiptText, UserRound, XCircle } from "lucide-react";
import StatusChip, { type StatusTone } from "@/components/workspace/StatusChip";
import type { SalesOrder } from "@/lib/salesOrderTypes";
import ProvisioningStatus from "./ProvisioningStatus";
import { salesOrderStatusLabel } from "./OrderList";

const statusTone: Record<string, StatusTone> = { draft: "blue", confirmed: "green", fulfilling: "blue", completed: "green", cancelled: "neutral" };

export default function OrderSummary({ order, busy, onEdit, onCancel, onRetry }: { order: SalesOrder; busy: boolean; onEdit: () => void; onCancel: () => void; onRetry: () => void }) {
  return (
    <article className="order-summary">
      <header className="order-summary__header">
        <div><p className="order-summary__eyebrow">销售订单</p><h2>{order.order_no}</h2><p>版本 {order.version} · 更新于 {order.updated_at || order.order_date}</p></div>
        <div className="order-summary__actions"><StatusChip tone={statusTone[order.status]}>{salesOrderStatusLabel[order.status] || order.status}</StatusChip>{order.status === "draft" && <button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={onEdit}><Pencil size={15} />编辑订单</button>}{["draft", "confirmed"].includes(order.status) && <button type="button" className="ui-button ui-button--danger" disabled={busy} onClick={onCancel}><XCircle size={15} />取消</button>}</div>
      </header>
      <ProvisioningStatus order={order} busy={busy} onRetry={onRetry} />
      <section className="order-summary__facts" aria-label="订单基本信息">
        <div><UserRound size={17} /><span>客户</span><strong>{order.customer_name}</strong><small>{order.project_name || "未填写项目"}</small></div>
        <div><CalendarDays size={17} /><span>交期</span><strong>{order.delivery_date || "未设置"}</strong><small>订单日期 {order.order_date}</small></div>
        <div><ReceiptText size={17} /><span>订单金额</span><strong>¥{order.total_amount.toLocaleString()}</strong><small>{order.door_count} 樘 · {order.line_count} 行</small></div>
        <div><MapPin size={17} /><span>交付信息</span><strong>{order.salesperson || "未填写销售员"}</strong><small>{order.delivery_address || "未填写收货地址"}</small></div>
      </section>
      <section className="order-summary__section">
        <div className="order-summary__section-title"><div><h3>门樘明细</h3><p>来源图纸、报价和确认快照可逐行追溯。</p></div><strong>{order.lines.length} 项</strong></div>
        <div className="order-summary__lines">{order.lines.map((line) => <div className={`order-summary-line${line.source_changed ? " has-warning" : ""}`} key={line.id || line.task_id}><div className="order-summary-line__main"><span className="order-summary-line__title"><strong>{line.line_no}. {line.product_name || line.door_type}</strong><StatusChip tone={line.source_type === "manual" ? "neutral" : "green"}>{line.source_type === "manual" ? "手工录入" : "终审图纸"}</StatusChip>{!line.quote_id && line.source_type === "drawing" && <StatusChip tone="amber">缺报价</StatusChip>}</span><p>{line.door_type || "未填门型"} · {line.width} × {line.height} mm · {line.opening_direction || "未填开向"} · {line.color || "未填颜色"}</p><small>{line.source_type === "drawing" ? `图纸 ${line.task_id} · 技术版本 ${line.drawing_revision || "未记录"}` : line.remark || "临时业务明细"}</small>{line.source_changed && <span className="order-summary-line__warning">来源图纸已变化，请取消原订单并重新确认。</span>}</div><div className="order-summary-line__amount"><span>{line.quantity} {line.unit}</span><strong>¥{line.amount.toLocaleString()}</strong></div></div>)}</div>
      </section>
      <section className="order-summary__bottom"><div><h3>收款节点</h3>{order.payment_nodes.length ? order.payment_nodes.map((node, index) => <div className="order-summary__payment" key={node.id || index}><span>{node.name}</span><span>{node.due_percent}%</span><strong>¥{node.due_amount.toLocaleString()}</strong><StatusChip tone={node.status === "已收款" ? "green" : "neutral"}>{node.status || "待收款"}</StatusChip></div>) : <p className="order-summary__muted">未配置收款节点</p>}</div><div className="order-summary__totals"><p><span>小计</span><strong>¥{order.subtotal.toLocaleString()}</strong></p><p><span>优惠</span><strong>-¥{order.discount_amount.toLocaleString()}</strong></p><p className="is-total"><span>订单总额</span><strong>¥{order.total_amount.toLocaleString()}</strong></p></div></section>
    </article>
  );
}
