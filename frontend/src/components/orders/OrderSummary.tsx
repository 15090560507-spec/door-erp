import { Banknote, CalendarDays, MapPin, Package, Pencil, Phone, ReceiptText, RotateCcw, UserRound, XCircle } from "lucide-react";
import StatusChip, { type StatusTone } from "@/components/workspace/StatusChip";
import { orderLineOverview } from "@/lib/salesOrderDisplay";
import { salesOrderChargeAmount } from "@/lib/salesOrderPricing";
import type { SalesOrder, SalesOrderReceipt } from "@/lib/salesOrderTypes";
import ProvisioningStatus from "./ProvisioningStatus";
import { salesOrderStatusLabel } from "./OrderList";
import OrderAttachmentSummary from "./OrderAttachmentSummary";
import OrderLineDetails from "./OrderLineDetails";

const statusTone: Record<string, StatusTone> = { draft: "blue", confirmed: "green", fulfilling: "blue", completed: "green", cancelled: "neutral" };

function readableTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function OrderSummary({ order, busy, onEdit, onCancel, onRetry, onReceipt, onReverseReceipt }: {
  order: SalesOrder; busy: boolean; onEdit: () => void; onCancel: () => void; onRetry: () => void;
  onReceipt: () => void; onReverseReceipt: (receipt: SalesOrderReceipt) => void;
}) {
  const charges = order.charge_lines || [];
  const receipts = order.receipts || [];
  return <article className="order-summary">
    <header className="order-summary__header">
      <div><p className="order-summary__eyebrow">销售订单</p><h2>{order.order_no}</h2><p>版本 {order.version} · 更新于 <time dateTime={order.updated_at || order.order_date} title={order.updated_at}>{readableTime(order.updated_at || order.order_date)}</time></p></div>
      <div className="order-summary__actions">
        <StatusChip tone={statusTone[order.status]}>{salesOrderStatusLabel[order.status] || order.status}</StatusChip>
        {["confirmed", "fulfilling", "completed"].includes(order.status) && <button type="button" className="ui-button ui-button--primary" disabled={busy || order.unpaid_amount <= 0.005} onClick={onReceipt}><Banknote size={16}/>登记收款</button>}
        {order.status === "draft" && <button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={onEdit}><Pencil size={16}/>编辑订单</button>}
        {["draft", "confirmed"].includes(order.status) && <button type="button" className="ui-button ui-button--danger" disabled={busy} onClick={onCancel}><XCircle size={16}/>取消</button>}
      </div>
    </header>
    <ProvisioningStatus order={order} busy={busy} onRetry={onRetry}/>

    <section className="order-summary__section" aria-labelledby="order-overview-heading">
      <SectionTitle id="order-overview-heading" number="01" title="订单概况"/>
      <dl className="order-summary__facts">
        <div><UserRound size={18}/><dt>客户 / 项目</dt><dd><strong>{order.customer_name}</strong><span>{order.project_name || "未填写项目"}</span></dd></div>
        <div><Phone size={18}/><dt>联系电话</dt><dd><strong>{order.customer_phone || "-"}</strong></dd></div>
        <div><Package size={18}/><dt>商品类别</dt><dd><strong>{order.product_category || "-"}</strong></dd></div>
        <div><CalendarDays size={18}/><dt>交期 / 订单日期</dt><dd><strong>{order.delivery_date || "未设置交期"}</strong><span>下单 {order.order_date}</span></dd></div>
        <div><ReceiptText size={18}/><dt>订单金额</dt><dd><strong>¥{order.total_amount.toLocaleString()}</strong><span>已收 ¥{order.paid_amount.toLocaleString()} · 未收 ¥{order.unpaid_amount.toLocaleString()}</span></dd></div>
        <div><MapPin size={18}/><dt>销售员 / 交付地址</dt><dd><strong>{order.salesperson || "未填写销售员"}</strong><span>{order.delivery_address || "未填写收货地址"}</span></dd></div>
      </dl>
      {order.remark && <div className="order-summary__remark"><span>订单备注</span><p>{order.remark}</p></div>}
    </section>

    <section className="order-summary__section" aria-labelledby="order-doors-heading">
      <SectionTitle id="order-doors-heading" number="02" title="门樘明细" count={`${order.lines.length} 项`}/>
      <div className="order-summary__lines">{order.lines.map(line => {
        const overview = orderLineOverview(line);
        return <article className={`order-summary-line${line.source_changed ? " has-warning" : ""}`} key={line.id || line.task_id}>
          <div className="order-summary-line__heading">
            <div className="order-summary-line__identity"><h4>{line.line_code || `${order.order_no}-${String(line.line_no).padStart(2, "0")}`}</h4><span>{overview.product}</span>
              <div className="order-summary-line__badges"><StatusChip tone={line.source_type === "manual" ? "neutral" : "green"}>{line.source_type === "manual" ? "手工录入" : "终审图纸"}</StatusChip>{!line.quote_id && line.source_type === "drawing" && <StatusChip tone="amber">缺报价</StatusChip>}</div>
            </div>
            <div className="order-summary-line__overview" aria-label="门樘简要信息"><strong>{overview.doorType} · {overview.dimensions}</strong><span>{overview.opening} · {overview.color}</span></div>
            <div className="order-summary-line__amount"><span>{line.quantity} {line.unit}</span><strong>¥{line.amount.toLocaleString()}</strong></div>
          </div>
          <OrderLineDetails line={line}/>
          {line.source_changed && <p className="order-summary-line__warning" role="alert">来源图纸已变化，请取消原订单并重新确认。</p>}
          {line.source_type === "drawing" && <details className="order-summary-line__source"><summary>来源记录</summary><dl><div><dt>来源图纸</dt><dd>{line.task_id}</dd></div><div><dt>技术版本</dt><dd>{line.drawing_revision || "未记录"}</dd></div>{line.quote_id && <div><dt>报价单</dt><dd>#{line.quote_id}</dd></div>}</dl></details>}
        </article>;
      })}</div>
    </section>

    <section className="order-summary__section" aria-labelledby="order-prices-heading">
      <SectionTitle id="order-prices-heading" number="03" title="价格明细" count={`${charges.length} 项`}/>
      {charges.length ? <div className="order-summary__charges" role="table" aria-label="订单价格明细">
        <div className="order-summary__charge-header" role="row"><span role="columnheader">品名 / 项目</span><span role="columnheader">规格 / 用量 / 单价</span><span role="columnheader">金额</span></div>
        {charges.map((charge, index) => <div className="order-summary__charge" role="row" key={charge.id || index}>
          <div className="order-summary__charge-name" role="cell"><strong>{charge.product_name}</strong><span>{charge.item_type}</span></div>
          <div className="order-summary__charge-spec" role="cell"><span>{charge.specification || "无规格"}</span><span>{charge.quantity} {charge.unit} × ¥{charge.unit_price.toLocaleString()}</span></div>
          <strong className="order-summary__charge-amount" role="cell">¥{Number(charge.amount ?? salesOrderChargeAmount(charge)).toLocaleString()}</strong>
        </div>)}
      </div> : <p className="order-summary__muted">暂无价格明细</p>}
    </section>

    <section className="order-summary__section" aria-labelledby="order-receipts-heading">
      <SectionTitle id="order-receipts-heading" number="04" title="收款信息"/>
      <div className="order-summary__settlement"><div className="order-summary__payment-details">
        <div><h4>收款计划</h4>{order.payment_nodes.length ? order.payment_nodes.map((node, index) => <div className="order-summary__payment" key={node.id || index}>
          <span>{node.name}</span><strong>¥{node.due_amount.toLocaleString()}</strong><span>{node.planned_date || "未定日期"}</span>
          <StatusChip tone={node.status === "paid" ? "green" : node.status === "partial" ? "amber" : "neutral"}>{node.status === "paid" ? "已收" : node.status === "partial" ? `已收 ¥${Number(node.paid_amount || 0).toLocaleString()}` : "待收"}</StatusChip>
        </div>) : <p className="order-summary__muted">未配置收款计划</p>}</div>
        <div className="order-summary__receipts"><div className="order-summary__receipts-title"><h4>实际收款</h4><span>{receipts.filter(item => item.status === "confirmed").length} 笔有效</span></div>
          {receipts.length ? receipts.map(receipt => <div className={`order-summary__receipt${receipt.status === "reversed" ? " is-reversed" : ""}`} key={receipt.id}>
            <span><strong>{receipt.receipt_no}</strong><small>{receipt.receipt_date} · {receipt.payment_method || "未填方式"}{receipt.reference ? ` · ${receipt.reference}` : ""}</small></span><strong>¥{Number(receipt.allocation_amount || 0).toLocaleString()}</strong>
            {receipt.status === "confirmed" ? <button type="button" title="冲销收款" aria-label={`冲销收款单 ${receipt.receipt_no}`} disabled={busy} onClick={() => onReverseReceipt(receipt)}><RotateCcw size={16}/></button> : <StatusChip tone="neutral">已冲销</StatusChip>}
          </div>) : <p className="order-summary__muted">尚未登记实际收款</p>}
        </div>
      </div><div className="order-summary__totals" aria-label="订单金额汇总">
        <p><span>小计</span><strong>¥{order.subtotal.toLocaleString()}</strong></p><p><span>优惠</span><strong>-¥{order.discount_amount.toLocaleString()}</strong></p>
        <p className="is-total"><span>订单总额</span><strong>¥{order.total_amount.toLocaleString()}</strong></p><p className="is-paid"><span>已收</span><strong>¥{order.paid_amount.toLocaleString()}</strong></p><p className="is-unpaid"><span>未收</span><strong>¥{order.unpaid_amount.toLocaleString()}</strong></p>
      </div></div>
    </section>

    <OrderAttachmentSummary orderId={order.id} attachments={order.attachments || []}/>
  </article>;
}

function SectionTitle({ id, number, title, count }: { id: string; number: string; title: string; count?: string }) {
  return <div className="order-summary__section-title"><span className="order-summary__section-number" aria-hidden="true">{number}</span><h3 id={id}>{title}</h3>{count && <span className="order-summary__section-count">{count}</span>}</div>;
}
