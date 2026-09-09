"use client";

import { CircleAlert, ClipboardCheck, PackageCheck, Plus, RefreshCw, Search, Send } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/workspace/EmptyState";
import FilterBar from "@/components/workspace/FilterBar";
import MasterDetail from "@/components/workspace/MasterDetail";
import MetricStrip from "@/components/workspace/MetricStrip";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import WorkspaceHeader from "@/components/workspace/WorkspaceHeader";
import { useAuth } from "@/hooks/useAuth";
import { cancelSalesOrder, confirmSalesOrder, createSalesOrder, getSalesOrder, getSalesOrderCandidates, getSalesOrders, retrySalesOrderProvisioning, updateSalesOrder } from "@/lib/salesOrderApi";
import type { SalesOrder, SalesOrderCandidate, SalesOrderEditor, SalesOrderEditorLine, SalesOrderPayload, SalesOrderQuoteChoice, SalesOrderSummary, SalesOrderValidationWarning } from "@/lib/salesOrderTypes";
import ApprovedSourcePicker from "./ApprovedSourcePicker";
import OrderEditor from "./OrderEditor";
import OrderList, { salesOrderStatusLabel } from "./OrderList";
import OrderSummary from "./OrderSummary";

const today = () => new Date().toISOString().slice(0, 10);

function emptyEditor(name = ""): SalesOrderEditor {
  return {
    order_date: today(), customer_name: "", project_name: "", delivery_address: "", salesperson: name,
    delivery_date: "", payment_template: "定金50%，发货前付清", remark: "", discount_amount: 0, lines: [],
    payment_nodes: [{ name: "定金", due_percent: 50, due_amount: 0, planned_date: "", remark: "" }, { name: "发货款", due_percent: 50, due_amount: 0, planned_date: "", remark: "" }],
  };
}

function manualLine(): SalesOrderEditorLine {
  return {
    source_type: "manual", task_id: `manual:${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    product_name: "", door_type: "", width: 0, height: 0, opening_direction: "", color: "",
    drawing_status: "手工录入", quote_id: null, quote_group_index: null, quoteChoices: [], quantity: 1,
    unit: "樘", unit_price: 0, remark: "",
  };
}

function apiMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error && "userMessage" in error) return String((error as { userMessage?: string }).userMessage || fallback);
  return error instanceof Error ? error.message : fallback;
}

function orderToEditor(order: SalesOrder): SalesOrderEditor {
  return {
    order_date: order.order_date, customer_name: order.customer_name, project_name: order.project_name,
    delivery_address: order.delivery_address, salesperson: order.salesperson, delivery_date: order.delivery_date,
    payment_template: order.payment_template, remark: order.remark, discount_amount: order.discount_amount,
    lines: order.lines.map((line) => ({
      ...line,
      drawing_status: line.current_drawing_status || line.drawing_status,
      quoteChoices: line.quote_choices?.length ? line.quote_choices : line.quote_id ? [{ quote_id: line.quote_id, quote_date: "", updated_at: "", group_index: line.quote_group_index || 0, group_name: "当前报价", amount: line.unit_price } satisfies SalesOrderQuoteChoice] : [],
    })),
    payment_nodes: order.payment_nodes.map((node) => ({ name: node.name, due_percent: node.due_percent, due_amount: node.due_amount, planned_date: node.planned_date, remark: node.remark })),
  };
}

function validationWarnings(editor: SalesOrderEditor, total: number): SalesOrderValidationWarning[] {
  const warnings: SalesOrderValidationWarning[] = [];
  if (!editor.customer_name.trim()) warnings.push({ key: "customer", message: "客户名称不能为空" });
  if (!editor.delivery_date) warnings.push({ key: "delivery", message: "订单交期不能为空" });
  if (!editor.lines.length) warnings.push({ key: "lines", message: "至少需要一项订单明细" });
  editor.lines.forEach((line, index) => {
    const lineNo = index + 1;
    if (!line.product_name.trim()) warnings.push({ key: `product-${lineNo}`, lineNo, message: `第 ${lineNo} 项产品名称不能为空` });
    if (line.source_type === "drawing" && !line.quote_id) warnings.push({ key: `quote-${lineNo}`, lineNo, message: `第 ${lineNo} 项请选择对应报价单` });
    if (line.width <= 0 || line.height <= 0) warnings.push({ key: `size-${lineNo}`, lineNo, message: `第 ${lineNo} 项宽、高必须大于 0` });
    if (line.quantity <= 0) warnings.push({ key: `qty-${lineNo}`, lineNo, message: `第 ${lineNo} 项数量必须大于 0` });
    if (line.unit_price <= 0) warnings.push({ key: `price-${lineNo}`, lineNo, message: `第 ${lineNo} 项单价必须大于 0` });
    if (line.source_changed) warnings.push({ key: `changed-${lineNo}`, lineNo, message: `第 ${lineNo} 项图纸版本已变化，请先保存草稿刷新快照` });
  });
  if (total <= 0) warnings.push({ key: "total", message: "订单总金额必须大于 0" });
  return warnings;
}

export default function OrdersWorkspace() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<SalesOrderSummary[]>([]);
  const [selected, setSelected] = useState<SalesOrder | null>(null);
  const [editor, setEditor] = useState<SalesOrderEditor>(() => emptyEditor());
  const [editing, setEditing] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [candidateOpen, setCandidateOpen] = useState(false);
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [candidates, setCandidates] = useState<SalesOrderCandidate[]>([]);
  const [candidateQuery, setCandidateQuery] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [notice, setNotice] = useState<{ title: string; message: string; error?: boolean } | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try { setOrders(await getSalesOrders({ q: query, status })); }
    catch (error) { setNotice({ title: "加载失败", message: apiMessage(error, "订单列表加载失败"), error: true }); }
    finally { setLoading(false); }
  }, [query, status]);

  useEffect(() => { const timer = window.setTimeout(() => { void loadOrders(); }, 180); return () => window.clearTimeout(timer); }, [loadOrders]);

  const subtotal = useMemo(() => editor.lines.reduce((sum, line) => sum + line.quantity * line.unit_price, 0), [editor.lines]);
  const total = Math.max(0, subtotal - Number(editor.discount_amount || 0));
  const warnings = useMemo(() => validationWarnings(editor, total), [editor, total]);
  const metrics = useMemo(() => ({
    draft: orders.filter((item) => item.status === "draft").length,
    confirmed: orders.filter((item) => item.status === "confirmed").length,
    fulfilling: orders.filter((item) => item.status === "fulfilling").length,
    dueRisk: orders.filter((item) => !["cancelled", "completed"].includes(item.status) && item.delivery_date && item.delivery_date <= today()).length,
  }), [orders]);
  const pickedCustomer = candidates.find((candidate) => picked.has(candidate.task_id))?.customer_name || "";
  const establishedCustomer = editor.customer_name || pickedCustomer;

  const chooseOrder = async (orderId: number) => {
    setBusy(true);
    try { const order = await getSalesOrder(orderId); setSelected(order); setEditor(orderToEditor(order)); setEditing(false); }
    catch (error) { setNotice({ title: "加载失败", message: apiMessage(error, "订单详情加载失败"), error: true }); }
    finally { setBusy(false); }
  };

  const fetchCandidates = async (customer = establishedCustomer) => {
    setCandidateLoading(true);
    try { setCandidates(await getSalesOrderCandidates({ q: candidateQuery, customer: customer || undefined, current_order_id: selected?.id })); }
    catch (error) { setNotice({ title: "加载失败", message: apiMessage(error, "候选图纸加载失败"), error: true }); }
    finally { setCandidateLoading(false); }
  };

  const openCandidates = () => { setCandidateOpen(true); setPicked(new Set()); void fetchCandidates(editor.customer_name); };
  const startNew = () => {
    setSelected(null); setEditor(emptyEditor(user?.name || "")); setEditing(true); setCandidateOpen(true); setPicked(new Set()); setCandidateQuery(""); setCandidateLoading(true);
    getSalesOrderCandidates().then(setCandidates).catch((error) => setNotice({ title: "加载失败", message: apiMessage(error, "候选图纸加载失败"), error: true })).finally(() => setCandidateLoading(false));
  };

  const toggleCandidate = (candidate: SalesOrderCandidate) => {
    const expectedCustomer = editor.customer_name || candidates.find((item) => picked.has(item.task_id))?.customer_name || candidate.customer_name;
    if (candidate.customer_name !== expectedCustomer) { setNotice({ title: "客户不一致", message: `当前订单客户为“${expectedCustomer}”，不能同时加入“${candidate.customer_name}”的图纸。`, error: true }); return; }
    setPicked((current) => { const next = new Set(current); if (next.has(candidate.task_id)) next.delete(candidate.task_id); else next.add(candidate.task_id); return next; });
  };

  const addPicked = () => {
    const selectedCandidates = candidates.filter((candidate) => picked.has(candidate.task_id));
    const existingIds = new Set(editor.lines.map((line) => line.task_id));
    const additions = selectedCandidates.filter((candidate) => !existingIds.has(candidate.task_id)).map((candidate): SalesOrderEditorLine => {
      const quote = candidate.quotes[0];
      return { source_type: "drawing", task_id: candidate.task_id, product_name: candidate.product_name, door_type: candidate.door_type, width: candidate.width, height: candidate.height, opening_direction: candidate.opening_direction, color: candidate.color, drawing_status: candidate.drawing_status, source_approved_at: candidate.approved_at, quote_id: quote?.quote_id || null, quote_group_index: quote?.group_index ?? null, quoteChoices: candidate.quotes, quantity: 1, unit: "樘", unit_price: quote?.amount || 0, remark: "" };
    });
    setEditor((current) => ({ ...current, customer_name: current.customer_name || selectedCandidates[0]?.customer_name || "", project_name: current.project_name || selectedCandidates[0]?.project_name || "", lines: [...current.lines, ...additions] }));
    setCandidateOpen(false); setPicked(new Set());
  };

  const payload = (): SalesOrderPayload => ({ ...editor, lines: editor.lines.map((line) => ({ source_type: line.source_type, task_id: line.task_id, quote_id: line.quote_id, quote_group_index: line.quote_group_index, quantity: line.quantity, product_name: line.product_name, door_type: line.door_type, width: line.width, height: line.height, opening_direction: line.opening_direction, color: line.color, unit: line.unit, unit_price: line.source_type === "manual" || line.quote_id ? line.unit_price : null, remark: line.remark })) });

  const save = async (closeAfter = true) => {
    if (!editor.lines.length) { setNotice({ title: "不能保存", message: "请先关联终审图纸，或添加一项手工明细。", error: true }); return null; }
    setBusy(true);
    try {
      const result = selected ? await updateSalesOrder(selected.id, payload()) : await createSalesOrder(payload());
      setSelected(result.order); setEditor(orderToEditor(result.order)); if (closeAfter) setEditing(false);
      setNotice({ title: "保存成功", message: result.message }); await loadOrders(); return result.order;
    } catch (error) { setNotice({ title: "保存失败", message: apiMessage(error, "订单草稿保存失败"), error: true }); return null; }
    finally { setBusy(false); }
  };

  const confirm = async () => {
    setConfirmOpen(false);
    const order = await save(false);
    if (!order) return;
    setBusy(true);
    try { const result = await confirmSalesOrder(order.id); setSelected(result.order); setEditor(orderToEditor(result.order)); setEditing(false); setNotice({ title: result.order.provisioning_status === "failed" ? "订单已确认，生成未完成" : "确认成功", message: result.message, error: result.order.provisioning_status === "failed" }); await loadOrders(); }
    catch (error) { setNotice({ title: "无法确认", message: apiMessage(error, "订单确认失败"), error: true }); }
    finally { setBusy(false); }
  };

  const retryProvisioning = async () => {
    if (!selected) return;
    setBusy(true);
    try { const result = await retrySalesOrderProvisioning(selected.id); setSelected(result.order); setEditor(orderToEditor(result.order)); setNotice({ title: "生成成功", message: result.message }); await loadOrders(); }
    catch (error) { const refreshed = await getSalesOrder(selected.id).catch(() => null); if (refreshed) setSelected(refreshed); setNotice({ title: "重新生成失败", message: apiMessage(error, "门樘和 BOM 生成失败"), error: true }); }
    finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!selected || !cancelReason.trim()) { setNotice({ title: "不能取消", message: "请填写取消原因", error: true }); return; }
    setBusy(true);
    try { const result = await cancelSalesOrder(selected.id, cancelReason.trim()); setSelected(result.order); setEditor(orderToEditor(result.order)); setCancelOpen(false); setCancelReason(""); setEditing(false); setNotice({ title: "订单已取消", message: result.message }); await loadOrders(); }
    catch (error) { setNotice({ title: "取消失败", message: apiMessage(error, "订单取消失败"), error: true }); }
    finally { setBusy(false); }
  };

  const backToList = () => { if (selected) setEditor(orderToEditor(selected)); else setEditor(emptyEditor(user?.name || "")); setEditing(false); };

  return <div className="min-h-screen bg-[#F5F5F7] text-[#1B1B1F]">
    <main className="workspace-page workspace-page--wide space-y-4">
      <WorkspaceHeader title="订单确认" description="关联已终审图纸及对应报价，确认后自动生成独立门樘生产编号与基础 BOM。" context={<><ClipboardCheck size={14} />经营管理 / 销售订单</>} actions={<><button type="button" className="ui-button ui-button--secondary" disabled={busy} onClick={() => void loadOrders()}><RefreshCw size={15} />刷新</button><button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={startNew}><Plus size={16} />新建订单</button></>} />
      <MetricStrip items={[{ key: "draft", label: "草稿", value: metrics.draft, tone: "blue", icon: <ClipboardCheck size={16} />, onClick: () => setStatus("draft") }, { key: "confirmed", label: "已确认", value: metrics.confirmed, tone: "green", icon: <PackageCheck size={16} />, onClick: () => setStatus("confirmed") }, { key: "fulfilling", label: "履约中", value: metrics.fulfilling, icon: <Send size={16} />, onClick: () => setStatus("fulfilling") }, { key: "risk", label: "交期风险", value: metrics.dueRisk, tone: "red", icon: <CircleAlert size={16} /> }]} />
      {!editing && <FilterBar summary={`共 ${orders.length} 张订单`}><label className="relative min-w-64 flex-1"><Search className="absolute left-3 top-2.5 text-[#777780]" size={16} /><input className="h-9 w-full pl-9 pr-3" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="订单号、客户、项目" /></label><select className="h-9 min-w-32 px-3" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">全部状态</option>{Object.entries(salesOrderStatusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></FilterBar>}
      {editing ? <OrderEditor order={selected} editor={editor} subtotal={subtotal} total={total} busy={busy} onBack={backToList} onFieldChange={(field, value) => setEditor((current) => ({ ...current, [field]: value }))} onPaymentChange={(index, changes) => setEditor((current) => ({ ...current, payment_nodes: current.payment_nodes.map((node, nodeIndex) => nodeIndex === index ? { ...node, ...changes } : node) }))} onAddSource={openCandidates} onAddManual={() => setEditor((current) => ({ ...current, lines: [...current.lines, manualLine()] }))} onLineChange={(index, changes) => setEditor((current) => ({ ...current, lines: current.lines.map((line, lineIndex) => lineIndex === index ? { ...line, ...changes } : line) }))} onLineRemove={(index) => setEditor((current) => ({ ...current, lines: current.lines.filter((_, lineIndex) => lineIndex !== index) }))} onSave={() => void save()} onConfirm={() => setConfirmOpen(true)} /> : <MasterDetail list={<OrderList orders={orders} selectedId={selected?.id} loading={loading} disabled={busy} onSelect={(orderId) => void chooseOrder(orderId)} onCreate={startNew} />} detail={selected ? <OrderSummary order={selected} busy={busy} onEdit={() => setEditing(true)} onCancel={() => setCancelOpen(true)} onRetry={() => void retryProvisioning()} /> : <EmptyState title="选择订单查看详情" description="可查看来源图纸、报价、门樘数量和履约生成状态。" />} listLabel="销售订单列表" detailLabel="销售订单摘要" />}
    </main>
    <ApprovedSourcePicker open={candidateOpen} candidates={candidates} loading={candidateLoading} query={candidateQuery} picked={picked} establishedCustomer={establishedCustomer} onQueryChange={setCandidateQuery} onSearch={() => void fetchCandidates()} onToggle={toggleCandidate} onAdd={addPicked} onManual={() => { setCandidateOpen(false); setEditor((current) => ({ ...current, lines: [...current.lines, manualLine()] })); }} onClose={() => setCandidateOpen(false)} />
    <ViewportDialog open={confirmOpen} title="请确认宽、高尺寸" description="正式确认后将冻结订单快照，并自动生成独立门樘和基础 BOM。" onClose={() => setConfirmOpen(false)} size="large" footer={<><button type="button" className="ui-button ui-button--secondary" onClick={() => setConfirmOpen(false)}>返回检查</button><button type="button" className="ui-button ui-button--primary" disabled={Boolean(warnings.length) || busy} onClick={() => void confirm()}><Send size={16} />确认无误并正式确认</button></>}><div className="order-confirm"><div className="order-confirm__lines">{editor.lines.map((line, index) => <div key={line.task_id}><span><strong>{index + 1}. {line.product_name || line.door_type || "未填写产品"}</strong><small>{line.width} × {line.height} mm · 数量 {line.quantity} {line.unit}</small></span><strong>¥{(line.quantity * line.unit_price).toLocaleString()}</strong></div>)}</div><div className="order-confirm__total"><span>订单总额</span><strong>¥{total.toLocaleString()}</strong></div>{warnings.length ? <div className="order-confirm__warnings" role="alert"><strong><CircleAlert size={16} />确认前还需处理 {warnings.length} 项</strong>{warnings.map((warning) => <p key={warning.key}>{warning.message}</p>)}</div> : <div className="order-confirm__ready"><PackageCheck size={17} /><span>尺寸、数量、报价和金额校验通过，可以正式确认。</span></div>}</div></ViewportDialog>
    <ViewportDialog open={cancelOpen} title="取消订单" description="取消后图纸可重新加入其他订单；已经进入履约的订单不能在此直接取消。" onClose={() => setCancelOpen(false)} size="small" footer={<><button type="button" className="ui-button ui-button--secondary" onClick={() => setCancelOpen(false)}>返回</button><button type="button" className="ui-button ui-button--danger" disabled={!cancelReason.trim() || busy} onClick={() => void cancel()}>确认取消</button></>}><label className="order-field"><span>取消原因<b>*</b></span><textarea value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="请说明取消原因" rows={4} /></label></ViewportDialog>
    <ViewportDialog open={Boolean(notice)} title={notice?.title || "提示"} onClose={() => setNotice(null)} size="small" footer={<button type="button" className="ui-button ui-button--primary" onClick={() => setNotice(null)}>知道了</button>}><p className={`whitespace-pre-wrap text-sm leading-6 ${notice?.error ? "text-[#B42318]" : "text-[#303036]"}`}>{notice?.message}</p></ViewportDialog>
    {busy && <div className="fixed inset-0 z-[190] cursor-wait bg-black/[0.025]" aria-hidden="true" />}
  </div>;
}
