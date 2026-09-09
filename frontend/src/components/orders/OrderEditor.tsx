import { ArrowLeft, FilePlus2, Link2, Save, Send } from "lucide-react";
import type { ReactNode } from "react";
import EmptyState from "@/components/workspace/EmptyState";
import StatusChip from "@/components/workspace/StatusChip";
import type { SalesOrder, SalesOrderEditor, SalesOrderEditorLine, SalesOrderPaymentNode } from "@/lib/salesOrderTypes";
import OrderLineEditor from "./OrderLineEditor";

function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return <label className="order-field"><span>{label}{required && <b>*</b>}</span>{children}</label>;
}

export default function OrderEditor({ order, editor, subtotal, total, busy, onBack, onFieldChange, onPaymentChange, onAddSource, onAddManual, onLineChange, onLineRemove, onSave, onConfirm }: {
  order: SalesOrder | null;
  editor: SalesOrderEditor;
  subtotal: number;
  total: number;
  busy: boolean;
  onBack: () => void;
  onFieldChange: (field: keyof SalesOrderEditor, value: string | number) => void;
  onPaymentChange: (index: number, changes: Partial<SalesOrderPaymentNode>) => void;
  onAddSource: () => void;
  onAddManual: () => void;
  onLineChange: (index: number, changes: Partial<SalesOrderEditorLine>) => void;
  onLineRemove: (index: number) => void;
  onSave: () => void;
  onConfirm: () => void;
}) {
  const locked = Boolean(order && order.status !== "draft");
  const drawingCustomer = editor.lines.find((line) => line.source_type === "drawing");
  return (
    <section className="order-editor">
      <header className="order-editor__header">
        <button type="button" className="ui-button ui-button--quiet" onClick={onBack}><ArrowLeft size={16} />返回订单列表</button>
        <div className="order-editor__heading"><div><p>{order ? "编辑销售订单" : "新建销售订单"}</p><h2>{order?.order_no || "订单草稿"}</h2><span>{order ? `版本 ${order.version}` : "默认从已终审图纸和报价创建"}</span></div>{order && <StatusChip tone={order.status === "draft" ? "blue" : "green"}>{order.status === "draft" ? "草稿" : order.status}</StatusChip>}</div>
        <div className="order-editor__actions"><button type="button" className="ui-button ui-button--secondary" disabled={busy || locked} onClick={onAddSource}><Link2 size={16} />关联图纸</button><button type="button" className="ui-button ui-button--secondary" disabled={busy || locked} onClick={onAddManual}><FilePlus2 size={16} />手工明细</button><button type="button" className="ui-button ui-button--secondary" disabled={busy || locked} onClick={onSave}><Save size={16} />保存草稿</button><button type="button" className="ui-button ui-button--primary" disabled={busy || locked || !editor.lines.length} onClick={onConfirm}><Send size={16} />正式确认</button></div>
      </header>

      <section className="order-editor__section">
        <div className="order-editor__section-title"><div><h3>订单信息</h3><p>带入后可调整项目、交期、交付和收款信息；技术结构仍以终审图纸为准。</p></div></div>
        <div className="order-editor__fields">
          <Field label="订单日期"><input disabled={locked} type="date" value={editor.order_date} onChange={(event) => onFieldChange("order_date", event.target.value)} /></Field>
          <Field label="客户" required><input disabled={locked || Boolean(drawingCustomer)} value={editor.customer_name} onChange={(event) => onFieldChange("customer_name", event.target.value)} placeholder={drawingCustomer ? "由首张终审图纸确定" : "请输入客户名称"} /></Field>
          <Field label="项目"><input disabled={locked} value={editor.project_name} onChange={(event) => onFieldChange("project_name", event.target.value)} /></Field>
          <Field label="交期" required><input disabled={locked} type="date" value={editor.delivery_date} onChange={(event) => onFieldChange("delivery_date", event.target.value)} /></Field>
          <Field label="销售员"><input disabled={locked} value={editor.salesperson} onChange={(event) => onFieldChange("salesperson", event.target.value)} /></Field>
          <Field label="收货地址"><input disabled={locked} value={editor.delivery_address} onChange={(event) => onFieldChange("delivery_address", event.target.value)} /></Field>
          <Field label="收款模板"><input disabled={locked} value={editor.payment_template} onChange={(event) => onFieldChange("payment_template", event.target.value)} /></Field>
          <Field label="订单备注"><input disabled={locked} value={editor.remark} onChange={(event) => onFieldChange("remark", event.target.value)} /></Field>
        </div>
      </section>

      <section className="order-editor__section">
        <div className="order-editor__section-title"><div><h3>门樘明细</h3><p>采购可按相同物料合并，生产、质检、入库和工资仍按每樘门追踪。</p></div><strong>{editor.lines.length} 项 · {editor.lines.reduce((sum, line) => sum + line.quantity, 0)} 樘</strong></div>
        <div className="order-editor__lines">{editor.lines.length ? editor.lines.map((line, index) => <OrderLineEditor key={line.task_id} line={line} index={index} disabled={locked || busy} onChange={(changes) => onLineChange(index, changes)} onRemove={() => onLineRemove(index)} />) : <EmptyState title="还没有订单明细" description="关联已终审图纸和报价，或为特殊情况添加手工明细。" action={<div className="flex flex-wrap justify-center gap-2"><button type="button" className="ui-button ui-button--primary" onClick={onAddSource}><Link2 size={16} />关联终审图纸</button><button type="button" className="ui-button ui-button--secondary" onClick={onAddManual}><FilePlus2 size={16} />手工录入</button></div>} />}</div>
      </section>

      <section className="order-editor__section order-editor__settlement">
        <div><div className="order-editor__section-title"><div><h3>收款节点</h3><p>第一版使用当前实际模板，确认前可调整比例和计划日期。</p></div></div><div className="order-editor__payments">{editor.payment_nodes.map((node, index) => <div key={index}><input disabled={locked} value={node.name} onChange={(event) => onPaymentChange(index, { name: event.target.value })} placeholder="节点名称" /><label><input disabled={locked} type="number" min="0" max="100" value={node.due_percent} onChange={(event) => onPaymentChange(index, { due_percent: Number(event.target.value) || 0 })} /><span>%</span></label><input disabled={locked} type="date" value={node.planned_date} onChange={(event) => onPaymentChange(index, { planned_date: event.target.value })} /></div>)}</div></div>
        <aside className="order-editor__totals"><p><span>订单小计</span><strong>¥{subtotal.toLocaleString()}</strong></p><label><span>优惠金额</span><input disabled={locked} type="number" min="0" value={editor.discount_amount} onChange={(event) => onFieldChange("discount_amount", Number(event.target.value) || 0)} /></label><p className="is-total"><span>订单总额</span><strong>¥{total.toLocaleString()}</strong></p></aside>
      </section>
      <footer className="order-editor__footer"><button type="button" className="ui-button ui-button--secondary" onClick={onBack}>返回</button><button type="button" className="ui-button ui-button--secondary" disabled={busy || locked} onClick={onSave}><Save size={16} />保存草稿</button><button type="button" className="ui-button ui-button--primary" disabled={busy || locked || !editor.lines.length} onClick={onConfirm}><Send size={16} />正式确认</button></footer>
    </section>
  );
}
