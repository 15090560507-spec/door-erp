"use client";

import { Banknote, CircleAlert, WandSparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import { apiErrorMessage } from "@/lib/api";
import { createSalesOrderReceipt, getSalesOrderReceiptCandidates } from "@/lib/salesOrderApi";
import type { SalesOrder, SalesOrderReceiptCandidate } from "@/lib/salesOrderTypes";

const today = () => new Date().toISOString().slice(0, 10);

export default function SalesReceiptDialog({ open, order, onClose, onSaved }: {
  open: boolean;
  order: SalesOrder;
  onClose: () => void;
  onSaved: (message: string) => Promise<void> | void;
}) {
  const [candidates, setCandidates] = useState<SalesOrderReceiptCandidate[]>([]);
  const [allocations, setAllocations] = useState<Record<number, number>>({});
  const [form, setForm] = useState({ receipt_date: today(), amount: 0, payment_method: "银行转账", reference: "", remark: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const allocated = useMemo(() => Object.values(allocations).reduce((sum, amount) => sum + Number(amount || 0), 0), [allocations]);

  useEffect(() => {
    if (!open) return;
    let active = true;
    getSalesOrderReceiptCandidates(order.customer_name)
      .then((rows) => { if (active) { setCandidates(rows); setAllocations(Object.fromEntries(rows.map((row) => [row.id, 0]))); } })
      .catch((cause) => { if (active) setError(apiErrorMessage(cause, "待分配订单加载失败")); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [open, order.customer_name]);

  const autoAllocate = () => {
    let remaining = Number(form.amount || 0);
    const sorted = [...candidates].sort((left, right) => left.id === order.id ? -1 : right.id === order.id ? 1 : left.order_date.localeCompare(right.order_date));
    const next: Record<number, number> = {};
    for (const candidate of sorted) {
      const amount = Math.min(candidate.unpaid_amount, Math.max(0, remaining));
      next[candidate.id] = Number(amount.toFixed(2));
      remaining = Number((remaining - amount).toFixed(2));
    }
    setAllocations(next);
  };

  const submit = async () => {
    setError("");
    if (form.amount <= 0) { setError("请输入实际收到的金额"); return; }
    if (Math.abs(allocated - form.amount) > 0.005) { setError(`订单分配合计 ¥${allocated.toFixed(2)} 必须等于收款金额 ¥${form.amount.toFixed(2)}`); return; }
    setBusy(true);
    try {
      const result = await createSalesOrderReceipt({ ...form, allocations: Object.entries(allocations).filter(([, amount]) => amount > 0).map(([orderId, amount]) => ({ order_id: Number(orderId), amount })) });
      await onSaved(result.message); onClose();
    } catch (cause) { setError(apiErrorMessage(cause, "收款登记失败")); }
    finally { setBusy(false); }
  };

  return <ViewportDialog open={open} title="登记实际收款" description={`客户：${order.customer_name}。一笔收款可分配到该客户的多张 TM 订单。`} size="large" onClose={onClose} footer={<><button type="button" className="ui-button ui-button--secondary" disabled={busy} onClick={onClose}>取消</button><button type="button" className="ui-button ui-button--primary" disabled={busy || form.amount <= 0 || Math.abs(allocated - form.amount) > 0.005} onClick={() => void submit()}><Banknote size={16}/>{busy ? "正在登记" : "确认收款"}</button></>}>
    <div className="sales-receipt-form">
      <div className="sales-receipt-form__fields">
        <label><span>收款日期 *</span><input type="date" value={form.receipt_date} onChange={(event) => setForm({ ...form, receipt_date: event.target.value })}/></label>
        <label><span>实收金额 *</span><input type="number" min="0" step="0.01" value={form.amount || ""} onChange={(event) => setForm({ ...form, amount: Number(event.target.value) || 0 })} placeholder="0.00"/></label>
        <label><span>收款方式</span><select value={form.payment_method} onChange={(event) => setForm({ ...form, payment_method: event.target.value })}>{["银行转账", "现金", "微信", "支付宝", "承兑", "其他"].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label><span>流水/凭证号</span><input value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} placeholder="可选"/></label>
      </div>
      <div className="sales-receipt-form__allocation-head"><div><strong>分配到订单</strong><p>只显示当前客户尚有欠款的已确认订单。</p></div><button type="button" className="ui-button ui-button--secondary" disabled={busy || form.amount <= 0} onClick={autoAllocate}><WandSparkles size={15}/>自动分配</button></div>
      <div className="sales-receipt-form__orders">{candidates.map((candidate) => <label key={candidate.id} className={candidate.id === order.id ? "is-current" : ""}><span><strong>{candidate.order_no}{candidate.id === order.id ? " · 当前订单" : ""}</strong><small>{candidate.project_name || "未填写项目"} · 订单 ¥{candidate.total_amount.toLocaleString()} · 已收 ¥{candidate.paid_amount.toLocaleString()}</small></span><span className="sales-receipt-form__unpaid">未收<strong>¥{candidate.unpaid_amount.toLocaleString()}</strong></span><input type="number" min="0" max={candidate.unpaid_amount} step="0.01" value={allocations[candidate.id] || ""} onChange={(event) => setAllocations({ ...allocations, [candidate.id]: Math.min(candidate.unpaid_amount, Number(event.target.value) || 0) })} placeholder="分配金额"/></label>)}{!busy && !candidates.length && <p className="sales-receipt-form__empty">该客户暂无可分配的欠款订单。</p>}</div>
      <div className="sales-receipt-form__balance"><span>收款 ¥{form.amount.toFixed(2)}</span><span>已分配 ¥{allocated.toFixed(2)}</span><strong className={Math.abs(allocated - form.amount) <= 0.005 ? "is-balanced" : ""}>差额 ¥{Math.abs(form.amount - allocated).toFixed(2)}</strong></div>
      <label className="sales-receipt-form__remark"><span>备注</span><textarea rows={2} value={form.remark} onChange={(event) => setForm({ ...form, remark: event.target.value })} placeholder="例如定金、发货尾款或特殊说明"/></label>
      {error && <p className="sales-receipt-form__error" role="alert"><CircleAlert size={15}/>{error}</p>}
    </div>
  </ViewportDialog>;
}
