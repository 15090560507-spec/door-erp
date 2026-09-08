"use client";

import { useCallback, useEffect, useMemo, useState, type ReactElement, type ReactNode } from "react";
import { useAuth } from "@/hooks/useAuth";
import { cancelSalesOrder, confirmSalesOrder, createSalesOrder, getSalesOrder, getSalesOrderCandidates, getSalesOrders, updateSalesOrder } from "@/lib/salesOrderApi";
import type { SalesOrder, SalesOrderCandidate, SalesOrderPayload, SalesOrderQuoteChoice, SalesOrderSummary } from "@/lib/salesOrderTypes";

type EditorLine = {
  source_type: "drawing" | "manual"; task_id: string; product_name: string; door_type: string; width: number; height: number;
  opening_direction: string; color: string; drawing_status: string; quote_id: number | null;
  quote_group_index: number | null; quoteChoices: SalesOrderQuoteChoice[]; quantity: number;
  unit: string; unit_price: number; remark: string; source_changed?: boolean;
};
type Editor = Omit<SalesOrderPayload, "lines"> & { lines: EditorLine[] };

const today = () => new Date().toISOString().slice(0, 10);
const statusLabel: Record<string, string> = { draft: "草稿", confirmed: "已确认", fulfilling: "履约中", completed: "已完成", cancelled: "已取消" };

function emptyEditor(name = ""): Editor {
  return {
    order_date: today(), customer_name: "", project_name: "", delivery_address: "", salesperson: name,
    delivery_date: "", payment_template: "定金50%，发货前付清", remark: "", discount_amount: 0, lines: [],
    payment_nodes: [
      { name: "定金", due_percent: 50, due_amount: 0, planned_date: "", remark: "" },
      { name: "发货款", due_percent: 50, due_amount: 0, planned_date: "", remark: "" },
    ],
  };
}

function manualLine(): EditorLine {
  return {
    source_type: "manual",
    task_id: `manual:${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    product_name: "", door_type: "", width: 0, height: 0, opening_direction: "", color: "",
    drawing_status: "手工录入", quote_id: null, quote_group_index: null, quoteChoices: [],
    quantity: 1, unit: "樘", unit_price: 0, remark: "",
  };
}

function apiMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error && "userMessage" in error) return String((error as { userMessage?: string }).userMessage || fallback);
  return error instanceof Error ? error.message : fallback;
}

function orderToEditor(order: SalesOrder): Editor {
  return {
    order_date: order.order_date, customer_name: order.customer_name, project_name: order.project_name,
    delivery_address: order.delivery_address, salesperson: order.salesperson, delivery_date: order.delivery_date,
    payment_template: order.payment_template, remark: order.remark, discount_amount: order.discount_amount,
    lines: order.lines.map((line) => ({
      ...line,
      drawing_status: line.current_drawing_status || line.drawing_status,
      quoteChoices: line.quote_choices?.length
        ? line.quote_choices
        : line.quote_id
          ? [{ quote_id: line.quote_id, quote_date: "", updated_at: "", group_index: line.quote_group_index || 0, group_name: "当前报价", amount: line.unit_price }]
          : [],
    })),
    payment_nodes: order.payment_nodes.map((node) => ({ name: node.name, due_percent: node.due_percent, due_amount: node.due_amount, planned_date: node.planned_date, remark: node.remark })),
  };
}

export default function OrdersPage() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<SalesOrderSummary[]>([]);
  const [selected, setSelected] = useState<SalesOrder | null>(null);
  const [editor, setEditor] = useState<Editor>(() => emptyEditor());
  const [editing, setEditing] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [candidateOpen, setCandidateOpen] = useState(false);
  const [candidates, setCandidates] = useState<SalesOrderCandidate[]>([]);
  const [candidateQ, setCandidateQ] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [notice, setNotice] = useState<{ title: string; message: string; error?: boolean } | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try { setOrders(await getSalesOrders({ q, status })); }
    catch (error) { setNotice({ title: "加载失败", message: apiMessage(error, "订单列表加载失败"), error: true }); }
    finally { setLoading(false); }
  }, [q, status]);

  useEffect(() => { void loadOrders(); }, [loadOrders]);

  const subtotal = useMemo(() => editor.lines.reduce((sum, line) => sum + line.quantity * line.unit_price, 0), [editor.lines]);
  const total = Math.max(0, subtotal - Number(editor.discount_amount || 0));
  const metrics = useMemo(() => ({
    draft: orders.filter((item) => item.status === "draft").length,
    confirmed: orders.filter((item) => item.status === "confirmed").length,
    fulfilling: orders.filter((item) => item.status === "fulfilling").length,
    dueRisk: orders.filter((item) => item.status !== "cancelled" && item.delivery_date && item.delivery_date <= today()).length,
  }), [orders]);

  const chooseOrder = async (orderId: number) => {
    setBusy(true);
    try {
      const order = await getSalesOrder(orderId);
      setSelected(order); setEditor(orderToEditor(order)); setEditing(true);
    } catch (error) { setNotice({ title: "加载失败", message: apiMessage(error, "订单详情加载失败"), error: true }); }
    finally { setBusy(false); }
  };

  const fetchCandidates = async () => {
    try {
      setCandidates(await getSalesOrderCandidates({ q: candidateQ, customer: editor.customer_name || undefined, current_order_id: selected?.id }));
    } catch (error) { setNotice({ title: "加载失败", message: apiMessage(error, "候选图纸加载失败"), error: true }); }
  };

  const openCandidates = () => {
    setCandidateOpen(true); setPicked(new Set()); void fetchCandidates();
  };

  const startNew = () => {
    setSelected(null); setEditor(emptyEditor(user?.name || "")); setEditing(true); setCandidateOpen(true); setPicked(new Set());
    getSalesOrderCandidates().then(setCandidates).catch((error) => setNotice({ title: "加载失败", message: apiMessage(error, "候选图纸加载失败"), error: true }));
  };

  const toggleCandidate = (candidate: SalesOrderCandidate) => {
    const expectedCustomer = editor.customer_name || candidates.find((item) => picked.has(item.task_id))?.customer_name || candidate.customer_name;
    if (candidate.customer_name !== expectedCustomer) {
      setNotice({ title: "客户不一致", message: "一张订单只能选择同一客户的图纸", error: true }); return;
    }
    setPicked((current) => {
      const next = new Set(current);
      if (next.has(candidate.task_id)) next.delete(candidate.task_id); else next.add(candidate.task_id);
      return next;
    });
  };

  const addPicked = () => {
    const selectedCandidates = candidates.filter((candidate) => picked.has(candidate.task_id));
    const existingIds = new Set(editor.lines.map((line) => line.task_id));
    const additions = selectedCandidates.filter((candidate) => !existingIds.has(candidate.task_id)).map((candidate): EditorLine => {
      const quote = candidate.quotes[0];
      return {
        source_type: "drawing",
        task_id: candidate.task_id, product_name: candidate.product_name, door_type: candidate.door_type,
        width: candidate.width, height: candidate.height, opening_direction: candidate.opening_direction, color: candidate.color,
        drawing_status: candidate.drawing_status, quote_id: quote?.quote_id || null, quote_group_index: quote?.group_index ?? null,
        quoteChoices: candidate.quotes, quantity: 1, unit: "樘", unit_price: quote?.amount || 0, remark: "",
      };
    });
    setEditor((current) => ({ ...current, customer_name: current.customer_name || selectedCandidates[0]?.customer_name || "", project_name: current.project_name || selectedCandidates[0]?.project_name || "", lines: [...current.lines, ...additions] }));
    setCandidateOpen(false);
  };

  const updateLine = (index: number, changes: Partial<EditorLine>) => setEditor((current) => ({ ...current, lines: current.lines.map((line, lineIndex) => lineIndex === index ? { ...line, ...changes } : line) }));

  const payload = (): SalesOrderPayload => ({
    ...editor,
    lines: editor.lines.map((line) => ({
      source_type: line.source_type,
      task_id: line.task_id,
      quote_id: line.quote_id,
      quote_group_index: line.quote_group_index,
      quantity: line.quantity,
      product_name: line.product_name,
      door_type: line.door_type,
      width: line.width,
      height: line.height,
      opening_direction: line.opening_direction,
      color: line.color,
      unit: line.unit,
      unit_price: line.source_type === "manual" || line.quote_id ? line.unit_price : null,
      remark: line.remark,
    })),
  });

  const save = async () => {
    if (!editor.lines.length) { setNotice({ title: "不能保存", message: "请先选择至少一张图纸", error: true }); return null; }
    setBusy(true);
    try {
      const result = selected ? await updateSalesOrder(selected.id, payload()) : await createSalesOrder(payload());
      setSelected(result.order); setEditor(orderToEditor(result.order)); setNotice({ title: "保存成功", message: result.message });
      await loadOrders(); return result.order;
    } catch (error) { setNotice({ title: "保存失败", message: apiMessage(error, "订单草稿保存失败"), error: true }); return null; }
    finally { setBusy(false); }
  };

  const confirm = async () => {
    setConfirmOpen(false);
    const order = await save();
    if (!order) return;
    setBusy(true);
    try {
      const result = await confirmSalesOrder(order.id);
      setSelected(result.order); setEditor(orderToEditor(result.order)); setNotice({ title: "确认成功", message: result.message }); await loadOrders();
    } catch (error) { setNotice({ title: "无法确认", message: apiMessage(error, "订单确认失败"), error: true }); }
    finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!selected || !cancelReason.trim()) {
      setNotice({ title: "不能取消", message: "请填写取消原因", error: true });
      return;
    }
    setBusy(true);
    try {
      const result = await cancelSalesOrder(selected.id, cancelReason.trim());
      setSelected(result.order); setEditor(orderToEditor(result.order)); setCancelOpen(false); setCancelReason("");
      setNotice({ title: "订单已取消", message: result.message }); await loadOrders();
    } catch (error) { setNotice({ title: "取消失败", message: apiMessage(error, "订单取消失败"), error: true }); }
    finally { setBusy(false); }
  };

  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]">
    <main className="workspace-page workspace-page--wide space-y-4">
      <header className="flex flex-wrap items-end gap-3">
        <div className="flex-1"><h1 className="text-xl font-semibold">订单确认</h1><p className="mt-1 text-sm text-[#636366]">关联已终审图纸及对应报价，或直接录入临时订单；确认后自动生成独立门樘与 BOM 草稿。</p></div>
        <button onClick={startNew} className="ui-button ui-button--primary">新建订单</button>
        <button onClick={() => void loadOrders()} className="h-9 border border-[#C7C7CC] bg-white px-4 text-sm">刷新</button>
      </header>
      <section className="grid grid-cols-2 gap-px border border-[#D1D1D6] bg-[#D1D1D6] md:grid-cols-4">
        <Metric label="草稿" value={metrics.draft} tone="blue" /><Metric label="已确认" value={metrics.confirmed} tone="green" /><Metric label="履约中" value={metrics.fulfilling} /><Metric label="交期风险" value={metrics.dueRisk} tone="red" />
      </section>
      <section className="grid min-h-[680px] gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="border border-[#D1D1D6] bg-white">
          <div className="border-b border-[#E5E5EA] p-4"><h2 className="font-semibold">销售订单</h2><div className="mt-3 grid grid-cols-[1fr_110px] gap-2"><input value={q} onChange={(event) => setQ(event.target.value)} placeholder="订单号、客户、项目" className="h-9 min-w-0 border border-[#C7C7CC] px-3 text-sm" /><select value={status} onChange={(event) => setStatus(event.target.value)} className="h-9 border border-[#C7C7CC] px-2 text-sm"><option value="">全部状态</option>{Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
          <div className="max-h-[720px] overflow-y-auto">{loading ? <Empty text="正在加载..." /> : orders.length ? orders.map((order) => <button key={order.id} onClick={() => void chooseOrder(order.id)} className={`block w-full border-b border-[#E5E5EA] p-4 text-left ${selected?.id === order.id ? "bg-[#EDF6FF]" : "hover:bg-[#F8F8FA]"}`}><div className="flex items-center justify-between gap-3"><strong className="text-sm">{order.order_no}</strong><Status value={order.status} /></div><div className="mt-2 truncate text-sm">{order.customer_name}{order.project_name ? ` · ${order.project_name}` : ""}</div><div className="mt-2 flex justify-between text-xs text-[#636366]"><span>{order.door_count} 樘 · 可下达 {order.releasable_count}</span><strong className="text-[#1C1C1E]">¥{order.total_amount.toLocaleString()}</strong></div></button>) : <Empty text="暂无订单，点击右上角新建" />}</div>
        </aside>
        <div className="min-w-0 border border-[#D1D1D6] bg-white">
          {!editing ? <Empty text="选择订单查看详情，或新建订单" tall /> : <div>
            <div className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] px-5 py-4"><div className="flex-1"><h2 className="font-semibold">{selected?.order_no || "新订单草稿"}</h2><p className="mt-1 text-xs text-[#636366]">{selected ? `版本 ${selected.version} · ${statusLabel[selected.status] || selected.status}` : "关联终审图纸或手工添加明细后保存"}</p></div>{selected && <Status value={selected.status} />}{selected && ["draft", "confirmed"].includes(selected.status) && <button disabled={busy} onClick={() => setCancelOpen(true)} className="h-9 border border-[#D70015] px-3 text-sm text-[#D70015] disabled:opacity-50">取消订单</button>}<button disabled={busy || Boolean(selected && selected.status !== "draft")} onClick={openCandidates} className="h-9 border border-[#007AFF] px-3 text-sm text-[#007AFF] disabled:border-[#D1D1D6] disabled:text-[#8E8E93]">关联终审图纸</button><button disabled={busy || Boolean(selected && selected.status !== "draft")} onClick={() => setEditor((current) => ({ ...current, lines: [...current.lines, manualLine()] }))} className="h-9 border border-[#C7C7CC] px-3 text-sm disabled:text-[#8E8E93]">手工添加</button><button disabled={busy || Boolean(selected && selected.status !== "draft")} onClick={() => void save()} className="h-9 border border-[#C7C7CC] px-4 text-sm disabled:text-[#8E8E93]">保存草稿</button><button disabled={busy || !editor.lines.length || Boolean(selected && selected.status !== "draft")} onClick={() => setConfirmOpen(true)} className="h-9 bg-[#007AFF] px-4 text-sm font-medium text-white disabled:bg-[#C7C7CC]">正式确认</button></div>
            <section className="border-b border-[#E5E5EA] p-5"><h3 className="text-sm font-semibold">基本信息</h3><div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Field label="订单日期"><input type="date" value={editor.order_date} onChange={(event) => setEditor({ ...editor, order_date: event.target.value })} /></Field><Field label="客户" required><input value={editor.customer_name} readOnly={editor.lines.some((line) => line.source_type === "drawing")} onChange={(event) => setEditor({ ...editor, customer_name: event.target.value })} placeholder={editor.lines.some((line) => line.source_type === "drawing") ? "由终审图纸带入" : "请输入客户名称"} /></Field><Field label="项目"><input value={editor.project_name} onChange={(event) => setEditor({ ...editor, project_name: event.target.value })} /></Field><Field label="交期" required><input type="date" value={editor.delivery_date} onChange={(event) => setEditor({ ...editor, delivery_date: event.target.value })} /></Field><Field label="销售员"><input value={editor.salesperson} onChange={(event) => setEditor({ ...editor, salesperson: event.target.value })} /></Field><Field label="收货地址"><input value={editor.delivery_address} onChange={(event) => setEditor({ ...editor, delivery_address: event.target.value })} /></Field><Field label="收款模板"><input value={editor.payment_template} onChange={(event) => setEditor({ ...editor, payment_template: event.target.value })} /></Field><Field label="订单备注"><input value={editor.remark} onChange={(event) => setEditor({ ...editor, remark: event.target.value })} /></Field></div></section>
            <section className="p-5">
              <div className="flex items-center justify-between"><div><h3 className="text-sm font-semibold">门樘明细</h3><p className="mt-1 text-xs text-[#636366]">终审图纸行必须关联报价；临时订单可使用手工明细，后续仍按每樘门生成独立编号。</p></div><span className="text-sm text-[#636366]">{editor.lines.length} 项</span></div>
              <div className="mt-4 space-y-3">{editor.lines.length ? editor.lines.map((line, index) => <div key={line.task_id} className={`border ${line.source_changed ? "border-[#D70015]" : "border-[#D1D1D6]"}`}>
                <div className="grid gap-3 bg-[#F7F7F9] px-4 py-3 md:grid-cols-[minmax(0,1fr)_auto]"><div><div className="flex flex-wrap items-center gap-2"><strong className="text-sm">{index + 1}. {line.product_name || line.door_type || "未填写产品"}</strong><Tag text={line.source_type === "manual" ? "手工明细" : "终审图纸"} good /><Tag text={line.drawing_status} good={line.source_type === "manual" || line.drawing_status === "已通过"} />{line.source_type === "drawing" && <Tag text={line.quote_id ? "已关联报价" : "未报价"} good={Boolean(line.quote_id)} />}{line.source_changed && <Tag text="图纸已变更，需重存草稿" good={false} />}</div><p className="mt-1 text-xs text-[#636366]">{line.door_type || "未填门型"} · {line.width || 0} × {line.height || 0} mm · {line.opening_direction || "未填开向"} · {line.color || "未填颜色"}</p></div>{selected?.status === "draft" || !selected ? <button onClick={() => setEditor((current) => ({ ...current, lines: current.lines.filter((_, lineIndex) => lineIndex !== index) }))} className="text-xs text-[#D70015]">移除</button> : null}</div>
                {line.source_type === "manual" && <div className="grid gap-3 border-b border-[#E5E5EA] p-4 sm:grid-cols-2 xl:grid-cols-6"><Field label="产品名称" required><input value={line.product_name} onChange={(event) => updateLine(index, { product_name: event.target.value })} /></Field><Field label="门型"><input value={line.door_type} onChange={(event) => updateLine(index, { door_type: event.target.value })} /></Field><Field label="宽(mm)" required><input type="number" min="0" value={line.width || ""} onChange={(event) => updateLine(index, { width: Number(event.target.value) || 0 })} /></Field><Field label="高(mm)" required><input type="number" min="0" value={line.height || ""} onChange={(event) => updateLine(index, { height: Number(event.target.value) || 0 })} /></Field><Field label="开向"><input value={line.opening_direction} onChange={(event) => updateLine(index, { opening_direction: event.target.value })} /></Field><Field label="颜色"><input value={line.color} onChange={(event) => updateLine(index, { color: event.target.value })} /></Field></div>}
                <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-5">{line.source_type === "drawing" ? <Field label="关联报价" required><select value={line.quote_id ? `${line.quote_id}:${line.quote_group_index || 0}` : ""} onChange={(event) => { const choice = line.quoteChoices.find((item) => `${item.quote_id}:${item.group_index}` === event.target.value); updateLine(index, { quote_id: choice?.quote_id || null, quote_group_index: choice?.group_index ?? null, unit_price: choice?.amount || 0 }); }}><option value="">未关联报价</option>{line.quoteChoices.map((choice) => <option key={`${choice.quote_id}-${choice.group_index}`} value={`${choice.quote_id}:${choice.group_index}`}>#{choice.quote_id} · {choice.quote_date} · ¥{choice.amount}</option>)}</select></Field> : <Field label="单位"><input value={line.unit} onChange={(event) => updateLine(index, { unit: event.target.value })} /></Field>}<Field label="数量" required><input type="number" min="1" value={line.quantity} onChange={(event) => updateLine(index, { quantity: Math.max(1, Number(event.target.value) || 1) })} /></Field><Field label="单价" required><input type="number" min="0" value={line.unit_price || ""} onChange={(event) => updateLine(index, { unit_price: Math.max(0, Number(event.target.value) || 0) })} /></Field><Field label="金额"><input value={`¥${(line.quantity * line.unit_price).toLocaleString()}`} readOnly /></Field><Field label="技术备注"><input value={line.remark} onChange={(event) => updateLine(index, { remark: event.target.value })} /></Field></div>
              </div>) : <div className="border border-dashed border-[#C7C7CC] py-12 text-center text-sm text-[#8E8E93]">尚未添加终审图纸或手工明细</div>}</div>
            </section>
            <section className="grid gap-5 border-t border-[#E5E5EA] p-5 lg:grid-cols-[1fr_340px]"><div><h3 className="text-sm font-semibold">收款节点</h3><div className="mt-3 space-y-2">{editor.payment_nodes.map((node, index) => <div key={index} className="grid gap-2 sm:grid-cols-[1fr_100px_140px]"><input value={node.name} onChange={(event) => setEditor((current) => ({ ...current, payment_nodes: current.payment_nodes.map((item, itemIndex) => itemIndex === index ? { ...item, name: event.target.value } : item) }))} placeholder="节点名称" className="h-9 border border-[#C7C7CC] px-3 text-sm" /><input type="number" min="0" max="100" value={node.due_percent} onChange={(event) => setEditor((current) => ({ ...current, payment_nodes: current.payment_nodes.map((item, itemIndex) => itemIndex === index ? { ...item, due_percent: Number(event.target.value) || 0 } : item) }))} className="h-9 border border-[#C7C7CC] px-3 text-sm" /><input type="date" value={node.planned_date} onChange={(event) => setEditor((current) => ({ ...current, payment_nodes: current.payment_nodes.map((item, itemIndex) => itemIndex === index ? { ...item, planned_date: event.target.value } : item) }))} className="h-9 border border-[#C7C7CC] px-3 text-sm" /></div>)}</div></div><div className="border-l border-[#E5E5EA] pl-5"><div className="flex justify-between py-2 text-sm"><span>订单小计</span><strong>¥{subtotal.toLocaleString()}</strong></div><label className="flex items-center justify-between gap-3 py-2 text-sm"><span>优惠金额</span><input type="number" min="0" value={editor.discount_amount} onChange={(event) => setEditor({ ...editor, discount_amount: Number(event.target.value) || 0 })} className="h-9 w-32 border border-[#C7C7CC] px-3 text-right" /></label><div className="mt-2 flex justify-between border-t border-[#1C1C1E] py-3 text-base"><strong>订单总额</strong><strong className="text-[#D70015]">¥{total.toLocaleString()}</strong></div></div></section>
          </div>}
        </div>
      </section>
    </main>
    {candidateOpen && <Modal title="选择候选图纸" onClose={() => setCandidateOpen(false)} wide><div className="flex gap-2"><input value={candidateQ} onChange={(event) => setCandidateQ(event.target.value)} placeholder="客户、项目、门型、图纸编号" className="h-9 min-w-0 flex-1 border border-[#C7C7CC] px-3 text-sm" /><button onClick={() => void fetchCandidates()} className="h-9 border border-[#C7C7CC] px-4 text-sm">搜索</button></div><div className="mt-4 max-h-[55vh] divide-y divide-[#E5E5EA] overflow-y-auto border border-[#D1D1D6]">{candidates.length ? candidates.map((candidate) => <label key={candidate.task_id} className="grid cursor-pointer grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-3 p-3 hover:bg-[#F7F7F9]"><input type="checkbox" checked={picked.has(candidate.task_id)} onChange={() => toggleCandidate(candidate)} /><div className="min-w-0"><strong className="text-sm">{candidate.customer_name} · {candidate.product_name}</strong><p className="mt-1 truncate text-xs text-[#636366]">{candidate.project_name || "未填项目"} · {candidate.door_type} · {candidate.width} × {candidate.height} · {candidate.task_id}</p></div><div className="text-right"><Tag text={candidate.drawing_status} good={candidate.drawing_status === "已通过"} /><p className={`mt-1 text-xs ${candidate.quotes.length ? "text-[#248A3D]" : "text-[#C76E00]"}`}>{candidate.quotes.length ? `报价 ¥${candidate.quotes[0].amount.toLocaleString()}` : "可先建草稿"}</p></div></label>) : <Empty text="没有可选图纸" />}</div><div className="mt-4 flex justify-end gap-2"><button onClick={() => setCandidateOpen(false)} className="h-9 border border-[#C7C7CC] px-4 text-sm">取消</button><button disabled={!picked.size} onClick={addPicked} className="h-9 bg-[#007AFF] px-4 text-sm text-white disabled:bg-[#C7C7CC]">加入订单（{picked.size}）</button></div></Modal>}
    {confirmOpen && <Modal title="请确认订单尺寸与金额" onClose={() => setConfirmOpen(false)}><div className="max-h-[45vh] divide-y divide-[#E5E5EA] overflow-y-auto border border-[#D1D1D6]">{editor.lines.map((line, index) => <div key={line.task_id} className="flex items-center justify-between gap-4 px-3 py-3 text-sm"><div><strong>{index + 1}. {line.product_name}</strong><p className="mt-1 text-xs text-[#636366]">{line.width} × {line.height} mm · 数量 {line.quantity}</p></div><strong>¥{(line.quantity * line.unit_price).toLocaleString()}</strong></div>)}</div><div className="mt-4 flex items-center justify-between border-t border-[#1C1C1E] pt-3"><strong>订单总额</strong><strong className="text-lg text-[#D70015]">¥{total.toLocaleString()}</strong></div><div className="mt-5 flex justify-end gap-2"><button onClick={() => setConfirmOpen(false)} className="h-9 border border-[#C7C7CC] px-4 text-sm">返回检查</button><button onClick={() => void confirm()} className="h-9 bg-[#007AFF] px-4 text-sm font-medium text-white">确认无误并正式确认</button></div></Modal>}
    {cancelOpen && <Modal title="取消订单" onClose={() => setCancelOpen(false)}><p className="text-sm text-[#636366]">取消后图纸可重新加入其他订单；已经下达生产的订单不能在这里直接取消。</p><textarea value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="请输入取消原因" className="mt-4 min-h-24 w-full border border-[#C7C7CC] p-3 text-sm" /><div className="mt-5 flex justify-end gap-2"><button onClick={() => setCancelOpen(false)} className="h-9 border border-[#C7C7CC] px-4 text-sm">返回</button><button disabled={!cancelReason.trim()} onClick={() => void cancel()} className="h-9 bg-[#D70015] px-4 text-sm text-white disabled:bg-[#C7C7CC]">确认取消</button></div></Modal>}
    {notice && <Modal title={notice.title} onClose={() => setNotice(null)}><p className={`whitespace-pre-wrap text-sm leading-6 ${notice.error ? "text-[#D70015]" : "text-[#1C1C1E]"}`}>{notice.message}</p><div className="mt-5 flex justify-end"><button onClick={() => setNotice(null)} className="h-9 bg-[#007AFF] px-4 text-sm text-white">知道了</button></div></Modal>}
    {busy && <div className="fixed inset-0 z-[70] cursor-wait bg-black/5" />}
  </div>;
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: "blue" | "green" | "red" }) { const color = tone === "blue" ? "text-[#007AFF]" : tone === "green" ? "text-[#248A3D]" : tone === "red" ? "text-[#D70015]" : "text-[#1C1C1E]"; return <div className="bg-white px-4 py-3"><div className="text-xs text-[#636366]">{label}</div><div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div></div>; }
function Status({ value }: { value: string }) { const active = value === "confirmed" || value === "fulfilling" || value === "completed"; return <span className={`px-2 py-1 text-xs font-medium ${active ? "bg-[#E7F7EA] text-[#248A3D]" : value === "cancelled" ? "bg-[#F2F2F7] text-[#8E8E93]" : "bg-[#EDF6FF] text-[#007AFF]"}`}>{statusLabel[value] || value}</span>; }
function Tag({ text, good }: { text: string; good: boolean }) { return <span className={`px-2 py-0.5 text-[11px] ${good ? "bg-[#E7F7EA] text-[#248A3D]" : "bg-[#FFF4E5] text-[#C76E00]"}`}>{text}</span>; }
function Field({ label, required, children }: { label: string; required?: boolean; children: ReactElement<{ className?: string }> }) { return <label className="block"><span className="mb-1 block text-xs text-[#636366]">{label}{required && <b className="ml-1 text-[#D70015]">*</b>}</span><span className="[&>input]:h-9 [&>input]:w-full [&>input]:border [&>input]:border-[#C7C7CC] [&>input]:px-3 [&>input]:text-sm [&>select]:h-9 [&>select]:w-full [&>select]:border [&>select]:border-[#C7C7CC] [&>select]:px-2 [&>select]:text-sm">{children}</span></label>; }
function Empty({ text, tall }: { text: string; tall?: boolean }) { return <div className={`flex items-center justify-center text-sm text-[#8E8E93] ${tall ? "min-h-[620px]" : "py-12"}`}>{text}</div>; }
function Modal({ title, children, onClose, wide }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) { return <div className="ui-dialog-backdrop" onMouseDown={onClose}><div className={`ui-dialog ${wide ? "ui-dialog--wide" : ""}`} onMouseDown={(event) => event.stopPropagation()}><div className="ui-dialog__header"><h3 className="ui-dialog__title">{title}</h3><button onClick={onClose} aria-label="关闭" className="ui-dialog__close">×</button></div><div className="ui-dialog__body">{children}</div></div></div>; }
