"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import TopNav from "@/components/TopNav";
import FulfillmentSupplyWorkbench from "@/components/FulfillmentSupplyWorkbench";
import { useAuth } from "@/hooks/useAuth";
import {
  confirmTechnicalPackage,
  batchFulfillmentWorkPackages,
  createFulfillmentChange,
  createFulfillmentException,
  createFulfillmentInspection,
  createFulfillmentShipment,
  finishedFulfillmentInbound,
  getDoorUnit,
  getFulfillmentDashboard,
  getFulfillmentOrder,
  getFulfillmentOrders,
  getFulfillmentPeople,
  getPendingFulfillmentTasks,
  releaseFulfillmentOrder,
  recordFulfillmentPayment,
  resolveFulfillmentException,
  saveTechnicalPackage,
  updateFulfillmentWorkPackage,
  updateFulfillmentSupply,
  signFulfillmentShipment,
} from "@/lib/fulfillmentApi";
import type {
  DoorUnitDetail,
  DoorUnitSummary,
  FulfillmentComponent,
  FulfillmentDashboard,
  FulfillmentOrder,
  FulfillmentPerson,
  FulfillmentWorkPackage,
  PendingFulfillmentTask,
} from "@/lib/fulfillmentTypes";

const STATUS_CARDS = ["待生产确认", "技术准备中", "备料与加工中", "可局部装配", "总装中", "待成品质检", "返工中", "待成品入库", "已入库待发货"];
export default function ProductionPage() {
  const { setModule } = useAuth();
  const [dashboard, setDashboard] = useState<FulfillmentDashboard | null>(null);
  const [pending, setPending] = useState<PendingFulfillmentTask[]>([]);
  const [orders, setOrders] = useState<FulfillmentOrder[]>([]);
  const [people, setPeople] = useState<FulfillmentPerson[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<FulfillmentOrder | null>(null);
  const [selectedDoor, setSelectedDoor] = useState<DoorUnitDetail | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ title: string; message: string; error: boolean } | null>(null);
  const [workspace, setWorkspace] = useState<"orders" | "purchase" | "warehouse">("orders");

  const notify = useCallback((message: string, error = false) => setNotice({ title: error ? "操作失败" : "操作成功", message, error }), []);
  const loadAll = useCallback(async () => {
    const [nextDashboard, nextPending, nextOrders, nextPeople] = await Promise.all([
      getFulfillmentDashboard(), getPendingFulfillmentTasks(), getFulfillmentOrders({ q, status }), getFulfillmentPeople(),
    ]);
    setDashboard(nextDashboard); setPending(nextPending); setOrders(nextOrders); setPeople(nextPeople);
  }, [q, status]);

  useEffect(() => { setModule("生产管理"); }, [setModule]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadAll().catch((error) => !cancelled && notify(apiMessage(error, "履约数据加载失败"), true)).finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [loadAll, notify]);

  const chooseOrder = async (id: number) => {
    setBusy(true);
    try {
      const order = await getFulfillmentOrder(id);
      setSelectedOrder(order); setSelectedDoor(null);
      const first = order.door_units?.[0];
      if (first) setSelectedDoor(await getDoorUnit(first.id));
    } catch (error) { notify(apiMessage(error, "订单详情加载失败"), true); }
    finally { setBusy(false); }
  };

  const chooseDoor = async (id: number) => {
    setBusy(true);
    try { setSelectedDoor(await getDoorUnit(id)); }
    catch (error) { notify(apiMessage(error, "门樘详情加载失败"), true); }
    finally { setBusy(false); }
  };

  const refresh = async (doorId?: number) => {
    await loadAll();
    if (selectedOrder) setSelectedOrder(await getFulfillmentOrder(selectedOrder.id));
    if (doorId || selectedDoor) setSelectedDoor(await getDoorUnit(doorId || selectedDoor!.id));
  };

  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]">
    <TopNav />
    <main className="mx-auto max-w-[1680px] space-y-4 px-4 py-5 sm:px-6">
      <header className="flex flex-wrap items-end gap-4">
        <div className="flex-1"><h1 className="text-xl font-semibold">门樘履约中心</h1><p className="mt-1 text-sm text-[#636366]">每樘门独立编号、独立技术版本和执行记录；整单负责人协调，执行人提交实际完成。</p></div>
        <button className="h-9 border border-[#C7C7CC] bg-white px-4 text-sm" onClick={() => void refresh()}>刷新</button>
      </header>

      <nav className="flex border border-[#D1D1D6] bg-white">
        {([['orders','门樘履约'],['purchase','采购'],['warehouse','仓库']] as const).map(([key,label]) => <button key={key} onClick={() => setWorkspace(key)} className={`h-11 min-w-28 border-r border-[#E5E5EA] px-5 text-sm ${workspace === key ? "bg-[#007AFF] text-white" : "bg-white text-[#3C3C43]"}`}>{label}</button>)}
      </nav>

      {workspace === "orders" && <><section className="grid grid-cols-2 gap-px border border-[#D1D1D6] bg-[#D1D1D6] md:grid-cols-4 xl:grid-cols-12">
        <Metric label="待下达" value={dashboard?.pending_release || 0} accent />
        {STATUS_CARDS.map((item) => <Metric key={item} label={item} value={dashboard?.status_counts?.[item] || 0} />)}
        <Metric label="未解决异常" value={dashboard?.open_exceptions || 0} danger />
        <Metric label="七日交期风险" value={dashboard?.due_risks || 0} warning />
      </section>

      {pending.length > 0 && <PendingPanel tasks={pending} busy={busy} onRelease={async (task, form) => {
        setBusy(true);
        try { const result = await releaseFulfillmentOrder(task.task_id, form); notify(result.message); await refresh(); await chooseOrder(result.order.id); }
        catch (error) { notify(apiMessage(error, "下达失败"), true); }
        finally { setBusy(false); }
      }} />}

      <section className="grid min-h-[640px] gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
        <aside className="border border-[#D1D1D6] bg-white">
          <div className="border-b border-[#E5E5EA] p-4"><h2 className="font-semibold">客户订单</h2><div className="mt-3 flex gap-2"><input value={q} onChange={(event) => setQ(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void loadAll()} placeholder="单号、客户、项目、生产编号" className="h-9 min-w-0 flex-1 border border-[#C7C7CC] px-3 text-sm" /><select value={status} onChange={(event) => setStatus(event.target.value)} className="h-9 w-32 border border-[#C7C7CC] px-2 text-sm"><option value="">全部状态</option>{STATUS_CARDS.map((item) => <option key={item}>{item}</option>)}</select></div></div>
          <div className="max-h-[710px] overflow-y-auto">
            {loading ? <Empty text="正在加载..." /> : orders.length === 0 ? <Empty text="暂无新履约订单" /> : orders.map((order) => <button key={order.id} onClick={() => void chooseOrder(order.id)} className={`block w-full border-b border-[#E5E5EA] p-4 text-left hover:bg-[#F8F8FA] ${selectedOrder?.id === order.id ? "bg-[#EDF6FF]" : "bg-white"}`}><div className="flex items-center justify-between gap-3"><strong className="text-sm">{order.order_no}</strong><Status text={order.representative_status || order.status} /></div><div className="mt-2 truncate text-sm">{order.customer}{order.project ? ` · ${order.project}` : ""}</div><div className="mt-2 flex justify-between text-xs text-[#636366]"><span>{order.door_count} 樘 · 已完成 {order.completed_count || 0}</span><span>{order.progress || 0}%</span></div><div className="mt-2 h-1.5 bg-[#E5E5EA]"><div className="h-full bg-[#007AFF]" style={{ width: `${order.progress || 0}%` }} /></div></button>)}
          </div>
        </aside>

        <div className="min-w-0 border border-[#D1D1D6] bg-white">
          {!selectedOrder ? <Empty text="选择左侧客户订单查看门樘履约详情" tall /> : <>
            <div className="border-b border-[#E5E5EA] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">{selectedOrder.order_no} · {selectedOrder.customer}</h2><p className="mt-1 text-sm text-[#636366]">{selectedOrder.project || "未填写项目"} · 交期 {selectedOrder.due_date || "未设置"}</p></div><span className="text-xs text-[#636366]">{selectedOrder.sales_note || "无销售备注"}</span></div><div className="mt-4 flex flex-wrap gap-2">{selectedOrder.door_units?.map((door) => <button key={door.id} onClick={() => void chooseDoor(door.id)} className={`min-w-44 border px-3 py-2 text-left ${selectedDoor?.id === door.id ? "border-[#007AFF] bg-[#EDF6FF]" : "border-[#D1D1D6] bg-white"}`}><div className="text-sm font-semibold">{door.production_no}</div><div className="mt-1 text-xs text-[#636366]">{door.product_name} · {door.specification}</div></button>)}</div></div>
            {selectedDoor ? <DoorUnitWorkbench door={selectedDoor} busy={busy} notify={notify} onBusy={setBusy} onChanged={async (next) => { setSelectedDoor(next); await refresh(next.id); }} /> : <Empty text="选择一个门樘生产单" tall />}
          </>}
        </div>
      </section>
      </>}
      {workspace === "purchase" && <FulfillmentSupplyWorkbench scope="purchase" notify={notify} />}
      {workspace === "warehouse" && <FulfillmentSupplyWorkbench scope="warehouse" notify={notify} />}
    </main>
    <datalist id="fulfillment-people">{people.map((person)=><option key={person.uid} value={person.uid}>{person.name} · {person.role}</option>)}</datalist>
    {busy && <div className="fixed bottom-5 right-5 z-40 border border-[#D1D1D6] bg-white px-4 py-3 text-sm shadow-lg">正在处理...</div>}
    {notice && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={() => setNotice(null)}><div className="w-full max-w-md border border-[#D1D1D6] bg-white p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}><h3 className="font-semibold">{notice.title}</h3><p className={`mt-3 whitespace-pre-wrap text-sm ${notice.error ? "text-[#C62828]" : "text-[#248A3D]"}`}>{notice.message}</p><div className="mt-5 text-right"><button onClick={() => setNotice(null)} className="h-9 bg-[#007AFF] px-5 text-sm text-white">知道了</button></div></div></div>}
  </div>;
}

function Metric({ label, value, accent, danger, warning }: { label: string; value: number; accent?: boolean; danger?: boolean; warning?: boolean }) {
  const tone = accent ? "text-[#007AFF]" : danger ? "text-[#C62828]" : warning ? "text-[#A05A00]" : "text-[#1C1C1E]";
  return <div className="bg-white px-3 py-3"><div className="truncate text-xs text-[#636366]">{label}</div><div className={`mt-1 text-xl font-semibold ${tone}`}>{value}</div></div>;
}

function PendingPanel({ tasks, busy, onRelease }: { tasks: PendingFulfillmentTask[]; busy: boolean; onRelease: (task: PendingFulfillmentTask, form: { due_date: string; sales_note: string; door_count: number; owner_uid: string }) => Promise<void> }) {
  const [open, setOpen] = useState<string | null>(null);
  const [form, setForm] = useState({ due_date: "", sales_note: "", door_count: 1, owner_uid: "" });
  return <section className="border border-[#B8D8F8] bg-[#F4F9FF] p-4"><div className="flex items-center justify-between"><div><h2 className="font-semibold">终审通过，待下达生产</h2><p className="mt-1 text-xs text-[#636366]">一张客户订单可生成多樘独立生产编号。</p></div><span className="text-sm font-semibold text-[#007AFF]">{tasks.length} 项</span></div><div className="mt-3 grid gap-2 lg:grid-cols-2">{tasks.map((task) => <div key={task.task_id} className="border border-[#D1D1D6] bg-white p-3"><div className="flex items-start justify-between gap-3"><div><div className="text-sm font-semibold">{task.customer || "未填写订货单位"}</div><div className="mt-1 text-xs text-[#636366]">{task.project || "未填写项目"} · {task.product_name || task.door_type} · {task.width}×{task.height}</div></div><button onClick={() => setOpen(open === task.task_id ? null : task.task_id)} className="h-8 bg-[#007AFF] px-3 text-xs text-white">下达</button></div>{open === task.task_id && <div className="mt-3 grid grid-cols-2 gap-2 border-t border-[#E5E5EA] pt-3"><label className="text-xs text-[#636366]">要求交期<input type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} className="mt-1 h-9 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]" /></label><label className="text-xs text-[#636366]">门樘数量<input type="number" min={1} max={50} value={form.door_count} onChange={(event) => setForm({ ...form, door_count: Math.max(1, Number(event.target.value) || 1) })} className="mt-1 h-9 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]" /></label><label className="text-xs text-[#636366]">整单负责人<input value={form.owner_uid} onChange={(event) => setForm({ ...form, owner_uid: event.target.value })} className="mt-1 h-9 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]" placeholder="用户账号或姓名" /></label><label className="text-xs text-[#636366]">销售备注<input value={form.sales_note} onChange={(event) => setForm({ ...form, sales_note: event.target.value })} className="mt-1 h-9 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]" /></label><button disabled={busy} onClick={() => void onRelease(task, form)} className="col-span-2 h-9 bg-[#007AFF] text-sm text-white disabled:opacity-50">确认下达并生成门樘生产单</button></div>}</div>)}</div></section>;
}

function DoorUnitWorkbench({ door, busy, notify, onBusy, onChanged }: { door: DoorUnitDetail; busy: boolean; notify: (message: string, error?: boolean) => void; onBusy: (value: boolean) => void; onChanged: (door: DoorUnitDetail) => Promise<void> }) {
  const [tab, setTab] = useState<"technical" | "work" | "supply" | "quality" | "delivery" | "exceptions" | "timeline">("technical");
  const packageData = door.technical_package;
  return <div><div className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] px-4 py-3"><div className="mr-auto"><div className="font-semibold">{door.production_no}</div><div className="mt-1 text-xs text-[#636366]">{door.product_name} · {door.specification} · {door.opening || "未填写开向"} · V{packageData?.version || 0}</div></div><Status text={door.status} /><span className="text-sm font-semibold text-[#007AFF]">{door.progress}%</span></div><div className="flex overflow-x-auto border-b border-[#E5E5EA] px-4">{([['technical','生产技术包'],['work','执行工作包'],['supply','供应与仓储'],['quality','质检与成品'],['delivery','财务与发货'],['exceptions',`异常 ${door.exceptions.filter((item) => item.status !== '已解决').length}`],['timeline','时间线']] as const).map(([key,label]) => <button key={key} onClick={() => setTab(key)} className={`shrink-0 border-b-2 px-4 py-3 text-sm ${tab === key ? "border-[#007AFF] text-[#007AFF]" : "border-transparent text-[#636366]"}`}>{label}</button>)}</div>
    <div className="p-4">{tab === "technical" && <TechnicalEditor door={door} busy={busy} notify={notify} onBusy={onBusy} onChanged={onChanged} />}{tab === "work" && <WorkBoard door={door} busy={busy} notify={notify} onBusy={onBusy} onChanged={onChanged} />}{tab === "supply" && <SupplyBoard door={door} busy={busy} notify={notify} onBusy={onBusy} onChanged={onChanged} />}{tab === "quality" && <QualityBoard door={door} busy={busy} notify={notify} onBusy={onBusy} onChanged={onChanged} />}{tab === "delivery" && <DeliveryBoard door={door} busy={busy} notify={notify} onBusy={onBusy} onChanged={onChanged} />}{tab === "exceptions" && <ExceptionBoard door={door} busy={busy} notify={notify} onBusy={onBusy} onChanged={onChanged} />}{tab === "timeline" && <Timeline door={door} />}</div>
  </div>;
}

function TechnicalEditor({ door, busy, notify, onBusy, onChanged }: WorkbenchProps) {
  const source = door.technical_package;
  const [summary, setSummary] = useState(source.product_summary);
  const [requirements, setRequirements] = useState(source.special_requirements);
  const [components, setComponents] = useState<FulfillmentComponent[]>(source.components);
  const [works, setWorks] = useState<FulfillmentWorkPackage[]>(source.work_packages);
  useEffect(() => { setSummary(source.product_summary); setRequirements(source.special_requirements); setComponents(source.components); setWorks(source.work_packages); }, [source]);
  const editable = source.status === "草稿";
  const persist = async (confirm = false) => { onBusy(true); try { let result = await saveTechnicalPackage(door.id, { product_summary: summary, special_requirements: requirements, components, work_packages: works }); if (confirm) result = await confirmTechnicalPackage(door.id); notify(result.message); await onChanged(result.door_unit); } catch (error) { notify(apiMessage(error, "技术包操作失败"), true); } finally { onBusy(false); } };
  const addComponent = () => setComponents([...components, { name: "", category: "其他", specification: "", quantity: 1, unit: "件", acquisition_method: "待确定", remark: "" }]);
  const addWork = () => setWorks([...works, { name: "", category: "生产", route: "", acquisition_method: "内部加工", executor_uid: "", planned_start: "", planned_end: "", opening_condition: "技术包确认", blocking_node: "", quantity: 1, unit: "项", piece_rate: 0, inspection_required: false, remark: "" }]);
  return <div className="space-y-5"><div className="grid gap-3 md:grid-cols-2"><label className="text-xs text-[#636366]">产品摘要<textarea disabled={!editable} value={summary} onChange={(event) => setSummary(event.target.value)} className="mt-1 min-h-20 w-full border border-[#C7C7CC] p-2 text-sm text-[#1C1C1E] disabled:bg-[#F2F2F7]" /></label><label className="text-xs text-[#636366]">特殊要求<textarea disabled={!editable} value={requirements} onChange={(event) => setRequirements(event.target.value)} className="mt-1 min-h-20 w-full border border-[#C7C7CC] p-2 text-sm text-[#1C1C1E] disabled:bg-[#F2F2F7]" /></label></div><EditableTable title="构件清单" editable={editable} onAdd={addComponent} columns={["名称","分类","规格","数量","单位","取得方式","操作"]}>{components.map((item,index) => <tr key={item.id || index} className="border-t border-[#E5E5EA]"><CellInput disabled={!editable} value={item.name} onChange={(value) => updateAt(components,setComponents,index,{name:value})} /><CellInput disabled={!editable} value={item.category} onChange={(value) => updateAt(components,setComponents,index,{category:value})} /><CellInput disabled={!editable} value={item.specification} onChange={(value) => updateAt(components,setComponents,index,{specification:value})} /><CellInput disabled={!editable} type="number" value={item.quantity} onChange={(value) => updateAt(components,setComponents,index,{quantity:Number(value)||0})} /><CellInput disabled={!editable} value={item.unit} onChange={(value) => updateAt(components,setComponents,index,{unit:value})} /><CellInput disabled={!editable} value={item.acquisition_method} onChange={(value) => updateAt(components,setComponents,index,{acquisition_method:value})} /><td className="px-2 py-2">{editable && <button onClick={() => setComponents(components.filter((_,i)=>i!==index))} className="text-xs text-[#C62828]">删除</button>}</td></tr>)}</EditableTable><EditableTable title="工作包" editable={editable} onAdd={addWork} columns={["名称","类别","路线","取得方式","执行人","计划完成","操作"]}>{works.map((item,index) => <tr key={item.id || index} className="border-t border-[#E5E5EA]"><CellInput disabled={!editable} value={item.name} onChange={(value) => updateAt(works,setWorks,index,{name:value})} /><CellInput disabled={!editable} value={item.category} onChange={(value) => updateAt(works,setWorks,index,{category:value})} /><CellInput disabled={!editable} value={item.route} onChange={(value) => updateAt(works,setWorks,index,{route:value})} /><CellInput disabled={!editable} value={item.acquisition_method} onChange={(value) => updateAt(works,setWorks,index,{acquisition_method:value})} /><CellInput disabled={!editable} value={item.executor_uid} onChange={(value) => updateAt(works,setWorks,index,{executor_uid:value})} /><CellInput disabled={!editable} type="date" value={item.planned_end} onChange={(value) => updateAt(works,setWorks,index,{planned_end:value})} /><td className="px-2 py-2">{editable && <button onClick={() => setWorks(works.filter((_,i)=>i!==index))} className="text-xs text-[#C62828]">删除</button>}</td></tr>)}</EditableTable>{editable ? <div className="flex justify-end gap-2"><button disabled={busy} onClick={() => void persist()} className="h-9 border border-[#C7C7CC] px-4 text-sm">保存草稿</button><button disabled={busy} onClick={() => void persist(true)} className="h-9 bg-[#007AFF] px-4 text-sm text-white">确认并冻结 V{source.version}</button></div> : <div className="flex items-center justify-between border border-[#B7E0BF] bg-[#F2FFF3] p-3 text-sm"><span>技术包 V{source.version} 已冻结，工作包已释放。</span><ChangeButton door={door} notify={notify} onBusy={onBusy} onChanged={onChanged} /></div>}</div>;
}

function WorkBoard({ door, busy, notify, onBusy, onChanged }: WorkbenchProps) {
  const works = door.technical_package?.work_packages || [];
  const [selected, setSelected] = useState<number[]>([]);
  const [executor, setExecutor] = useState("");
  const [remark, setRemark] = useState("");
  const grouped = useMemo(() => works.reduce<Record<string, FulfillmentWorkPackage[]>>((result, item) => {
    const key = item.status || "草稿";
    (result[key] ||= []).push(item);
    return result;
  }, {}), [works]);
  useEffect(() => { setSelected((current) => current.filter((id) => works.some((item) => item.id === id && !["已完成","已取消"].includes(item.status || "")))); }, [works]);
  const activeIds = works.filter((item) => item.id && !["已完成","已取消"].includes(item.status || "")).map((item) => item.id!);
  const runBatch = async (action: string) => {
    if (!selected.length) return notify("请先勾选工作包", true);
    let actionRemark = remark;
    if (action === "跳过" && !actionRemark.trim()) actionRemark = window.prompt("请输入跳过原因；该原因会写入履约记录") || "";
    if (action === "跳过" && !actionRemark.trim()) return;
    onBusy(true);
    try { const result = await batchFulfillmentWorkPackages(door.id, { work_ids: selected, action, executor_uid: executor, remark: actionRemark }); notify(result.message); setSelected([]); setRemark(""); await onChanged(result.door_unit); }
    catch (error) { notify(apiMessage(error, "批量更新工作包失败"), true); }
    finally { onBusy(false); }
  };
  return <div className="space-y-3"><section className="sticky top-14 z-20 border border-[#B8D8F8] bg-[#F4F9FF] p-3"><div className="flex flex-wrap items-center gap-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={activeIds.length > 0 && selected.length === activeIds.length} onChange={() => setSelected(selected.length === activeIds.length ? [] : activeIds)} />全选未完成</label><span className="text-xs text-[#636366]">已选 {selected.length} 项</span><input list="fulfillment-people" value={executor} onChange={(event) => setExecutor(event.target.value)} placeholder="统一执行人（可空）" className="h-9 w-44 border border-[#C7C7CC] bg-white px-2 text-sm"/><input value={remark} onChange={(event) => setRemark(event.target.value)} placeholder="批量说明（跳过时必填）" className="h-9 min-w-52 flex-1 border border-[#C7C7CC] bg-white px-2 text-sm"/>{["开始","提交质检","确认完成","跳过"].map((action)=><button key={action} disabled={busy||!selected.length} onClick={()=>void runBatch(action)} className={`h-9 px-3 text-sm text-white disabled:opacity-40 ${action === "跳过" ? "bg-[#8E8E93]" : action === "确认完成" ? "bg-[#248A3D]" : "bg-[#007AFF]"}`}>{action}</button>)}</div><p className="mt-2 text-xs text-[#636366]">无需逐级点击：不要求过程检验的工作包可直接确认完成；要求检验的工作包先提交质检。跳过必须留原因。</p></section><div className="grid gap-3 lg:grid-cols-3">{["待排单","已排单","进行中","待质检","已完成","暂停","异常","返工"].map((status) => <section key={status} className="border border-[#D1D1D6] bg-[#F8F8FA]"><div className="flex items-center justify-between border-b border-[#D1D1D6] px-3 py-2 text-sm font-semibold"><span>{status}</span><span className="text-xs text-[#636366]">{grouped[status]?.length || 0}</span></div><div className="space-y-2 p-2">{(grouped[status] || []).map((work) => <WorkCard key={work.id} work={work} busy={busy} selected={Boolean(work.id && selected.includes(work.id))} onSelect={(checked)=>work.id&&setSelected(checked?[...selected,work.id]:selected.filter((id)=>id!==work.id))} onSave={async (payload) => { if (!work.id) return; onBusy(true); try { const result=await updateFulfillmentWorkPackage(work.id,payload); notify(result.message); await onChanged(result.door_unit); } catch(error){ notify(apiMessage(error,"工作包更新失败"),true); } finally{onBusy(false);} }} />)}{!grouped[status]?.length && <div className="py-5 text-center text-xs text-[#8E8E93]">暂无</div>}</div></section>)}</div></div>;
}

function WorkCard({ work, busy, selected, onSelect, onSave }: { work: FulfillmentWorkPackage; busy: boolean; selected:boolean; onSelect:(checked:boolean)=>void; onSave: (payload: {status:string;executor_uid:string;actual_quantity?:number;remark:string})=>Promise<void> }) { const [executor,setExecutor]=useState(work.executor_uid||""); const [remark,setRemark]=useState(work.remark||""); const terminal=["已完成","已取消"].includes(work.status||""); const quick=work.status==="待质检"?"已完成":work.inspection_required?"待质检":work.status==="进行中"?"已完成":"进行中"; return <div className={`border bg-white p-3 ${selected?"border-[#007AFF]":"border-[#D1D1D6]"}`}><div className="flex items-start gap-2"><input type="checkbox" disabled={terminal} checked={selected} onChange={(event)=>onSelect(event.target.checked)} className="mt-1"/><div className="min-w-0 flex-1"><div className="text-sm font-semibold">{work.name}</div><div className="mt-1 text-xs text-[#636366]">{work.route||work.category} · {work.acquisition_method}{work.inspection_required?" · 需过程检验":""}</div></div></div>{!terminal&&<div className="mt-3 grid gap-2"><input list="fulfillment-people" value={executor} onChange={(e)=>setExecutor(e.target.value)} placeholder="执行人" className="h-8 border border-[#C7C7CC] px-2 text-xs"/><input value={remark} onChange={(e)=>setRemark(e.target.value)} placeholder="完成说明/异常说明" className="h-8 border border-[#C7C7CC] px-2 text-xs"/><button disabled={busy} onClick={()=>void onSave({status:quick,executor_uid:executor,actual_quantity:quick==="已完成"?work.quantity:undefined,remark})} className="h-8 bg-[#007AFF] text-xs text-white disabled:bg-[#C7C7CC]">{quick==="进行中"?"开始":quick==="待质检"?"提交质检":"确认完成"}</button></div>}</div>; }

function SupplyBoard({ door, busy, notify, onBusy, onChanged }: WorkbenchProps) {
  if (!door.supplies.length) return <Empty text="确认并冻结技术包后，系统会按构件清单生成供应事项" />;
  return <div className="space-y-3">{door.supplies.map((item) => <SupplyRow key={item.id} item={item} busy={busy} onSave={async(payload)=>{onBusy(true);try{const result=await updateFulfillmentSupply(item.id,payload);notify(result.message);await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"供应事项更新失败"),true);}finally{onBusy(false);}}} onInspect={async(result)=>{onBusy(true);try{const response=await createFulfillmentInspection(door.id,{inspection_type:"来料检验",result,target_name:item.name,quantity:item.actual_quantity||item.required_quantity,defect_detail:result==="不合格"?"来料不合格":"",remark:""});notify(response.message);await onChanged(response.door_unit);}catch(error){notify(apiMessage(error,"来料检验登记失败"),true);}finally{onBusy(false);}}} />)}<p className="text-xs text-[#636366]">流程：经办人办理 → 到货待检 → 独立来料检验 → 仓库登记入库。内部加工件也可按实际情况办理入库。</p></div>;
}

function SupplyRow({item,busy,onSave,onInspect}:{item:DoorUnitDetail["supplies"][number];busy:boolean;onSave:(payload:{status:string;handler_uid:string;supplier:string;actual_quantity?:number;unit_cost?:number;remark:string})=>Promise<void>;onInspect:(result:string)=>Promise<void>}) { const [state,setState]=useState({status:item.status,handler_uid:item.handler_uid,supplier:item.supplier,actual_quantity:item.actual_quantity||item.required_quantity,unit_cost:item.unit_cost||0,remark:item.remark}); useEffect(()=>setState({status:item.status,handler_uid:item.handler_uid,supplier:item.supplier,actual_quantity:item.actual_quantity||item.required_quantity,unit_cost:item.unit_cost||0,remark:item.remark}),[item]); return <div className="grid gap-2 border border-[#D1D1D6] p-3 md:grid-cols-[minmax(180px,1.5fr)_110px_120px_120px_100px_100px_auto]"><div><div className="text-sm font-semibold">{item.name}</div><div className="mt-1 text-xs text-[#636366]">{item.category} · {item.specification||"无规格"} · 需求 {item.required_quantity} {item.unit} · {item.acquisition_method}</div></div><input value={state.handler_uid} onChange={e=>setState({...state,handler_uid:e.target.value})} placeholder="经办人" className="h-9 border border-[#C7C7CC] px-2 text-xs"/><input value={state.supplier} onChange={e=>setState({...state,supplier:e.target.value})} placeholder="供应商/来源" className="h-9 border border-[#C7C7CC] px-2 text-xs"/><input type="number" value={state.actual_quantity} onChange={e=>setState({...state,actual_quantity:Number(e.target.value)||0})} className="h-9 border border-[#C7C7CC] px-2 text-xs"/><input type="number" value={state.unit_cost} onChange={e=>setState({...state,unit_cost:Number(e.target.value)||0})} placeholder="单价" className="h-9 border border-[#C7C7CC] px-2 text-xs"/><select value={state.status} onChange={e=>setState({...state,status:e.target.value})} className="h-9 border border-[#C7C7CC] px-2 text-xs"><option>待处理</option><option>办理中</option><option>到货待检</option><option>已入库</option><option>已发料</option><option>暂停</option><option>已取消</option></select><div className="flex gap-1"><button disabled={busy} onClick={()=>void onSave(state)} className="h-9 bg-[#007AFF] px-3 text-xs text-white">保存</button>{item.status==="到货待检"&&<><button disabled={busy} onClick={()=>void onInspect("合格")} className="h-9 border border-[#248A3D] px-2 text-xs text-[#248A3D]">合格</button><button disabled={busy} onClick={()=>void onInspect("不合格")} className="h-9 border border-[#C62828] px-2 text-xs text-[#C62828]">拒收</button></>}</div></div>; }

function QualityBoard({door,busy,notify,onBusy,onChanged}:WorkbenchProps){const [form,setForm]=useState({result:"合格",defect_detail:"",remark:""});const [inbound,setInbound]=useState({warehouse:"成品仓",location:"",quantity:1,remark:""});const latest=door.inspections.find(item=>item.inspection_type==="成品质检");const unfinished=door.unfinished_work_packages||[];return <div className="space-y-4">{unfinished.length>0&&<section className="border border-[#F0B8B8] bg-[#FFF5F5] p-3"><h3 className="text-sm font-semibold text-[#C62828]">当前版本还有 {unfinished.length} 个工作包未结束</h3><div className="mt-2 flex flex-wrap gap-2">{unfinished.map(item=><span key={item.id} className="border border-[#F0B8B8] bg-white px-2 py-1 text-xs text-[#8A2424]">{item.name} · {item.status}</span>)}</div><p className="mt-2 text-xs text-[#636366]">请到“执行工作包”批量完成，或填写原因后跳过；旧技术版本的暂停工作包不会阻塞本次质检。</p></section>}<section className="border border-[#D1D1D6] p-4"><div className="flex flex-wrap items-center gap-2"><h3 className="mr-auto text-sm font-semibold">成品质检</h3>{latest&&<><span className="text-xs text-[#636366]">最近：{formatTime(latest.created_at)}</span><Status text={latest.result}/></>}<select value={form.result} onChange={e=>setForm({...form,result:e.target.value})} className="h-9 border border-[#C7C7CC] px-2 text-sm"><option>合格</option><option>不合格</option><option>让步接收</option></select><input value={form.defect_detail} onChange={e=>setForm({...form,defect_detail:e.target.value})} placeholder="缺陷说明（不合格时必填）" className="h-9 min-w-56 border border-[#C7C7CC] px-2 text-sm"/><button disabled={busy||unfinished.length>0} onClick={async()=>{onBusy(true);try{const result=await createFulfillmentInspection(door.id,{inspection_type:"成品质检",result:form.result,target_name:door.production_no,quantity:1,defect_detail:form.defect_detail,remark:form.remark});notify(result.message);await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"成品质检登记失败"),true);}finally{onBusy(false);}}} className="h-9 bg-[#007AFF] px-4 text-sm text-white disabled:bg-[#C7C7CC]">提交质检</button></div></section><section className="border border-[#D1D1D6] p-4"><h3 className="text-sm font-semibold">成品入库</h3><div className="mt-3 grid gap-2 md:grid-cols-[160px_160px_100px_minmax(180px,1fr)_auto]"><input value={inbound.warehouse} onChange={e=>setInbound({...inbound,warehouse:e.target.value})} placeholder="仓库" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={inbound.location} onChange={e=>setInbound({...inbound,location:e.target.value})} placeholder="库位" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input type="number" value={inbound.quantity} onChange={e=>setInbound({...inbound,quantity:Number(e.target.value)||1})} className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={inbound.remark} onChange={e=>setInbound({...inbound,remark:e.target.value})} placeholder="入库备注" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><button disabled={busy||door.status!=="待成品入库"} onClick={async()=>{onBusy(true);try{const result=await finishedFulfillmentInbound(door.id,inbound);notify(result.message);await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"成品入库失败"),true);}finally{onBusy(false);}}} className="h-9 bg-[#007AFF] px-4 text-sm text-white disabled:bg-[#C7C7CC]">确认入库</button></div></section><SimpleRecords title="检验记录" rows={door.inspections.map(item=>[item.inspection_type,item.target_name||"-",item.result,item.inspector_uid,formatTime(item.created_at)])}/><SimpleRecords title="库存流水" rows={door.inventory_movements.map(item=>[item.movement_type,item.item_name,`${item.quantity} ${item.unit}`,`${item.warehouse} ${item.location}`,formatTime(item.created_at)])}/></div>;}

function DeliveryBoard({door,busy,notify,onBusy,onChanged}:WorkbenchProps){const [pay,setPay]=useState({amount:0,payment_date:new Date().toISOString().slice(0,10),reference:"",remark:""});const [ship,setShip]=useState({required_payment:0,carrier:"",vehicle_no:"",contact:"",authorization_reason:"",authorized_by:"",remark:""});return <div className="space-y-4"><div className="grid gap-4 lg:grid-cols-2"><section className="border border-[#D1D1D6] p-4"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">收款登记</h3><strong className="text-[#248A3D]">已收 ¥{door.paid_amount.toFixed(2)}</strong></div><div className="mt-3 grid grid-cols-2 gap-2"><input type="number" value={pay.amount} onChange={e=>setPay({...pay,amount:Number(e.target.value)||0})} placeholder="收款金额" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input type="date" value={pay.payment_date} onChange={e=>setPay({...pay,payment_date:e.target.value})} className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={pay.reference} onChange={e=>setPay({...pay,reference:e.target.value})} placeholder="凭证号" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><button disabled={busy||pay.amount<=0} onClick={async()=>{onBusy(true);try{const result=await recordFulfillmentPayment(door.id,pay);notify(result.message);setPay({...pay,amount:0,reference:""});await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"收款登记失败"),true);}finally{onBusy(false);}}} className="h-9 bg-[#007AFF] text-sm text-white disabled:bg-[#C7C7CC]">登记收款</button></div></section><section className="border border-[#D1D1D6] p-4"><h3 className="text-sm font-semibold">发货与财务放行</h3><div className="mt-3 grid grid-cols-2 gap-2"><input type="number" value={ship.required_payment} onChange={e=>setShip({...ship,required_payment:Number(e.target.value)||0})} placeholder="本次发货应收" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={ship.carrier} onChange={e=>setShip({...ship,carrier:e.target.value})} placeholder="物流/司机" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={ship.vehicle_no} onChange={e=>setShip({...ship,vehicle_no:e.target.value})} placeholder="车牌/运单" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={ship.contact} onChange={e=>setShip({...ship,contact:e.target.value})} placeholder="联系电话" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={ship.authorization_reason} onChange={e=>setShip({...ship,authorization_reason:e.target.value})} placeholder="特殊放行原因（可空）" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><input value={ship.authorized_by} onChange={e=>setShip({...ship,authorized_by:e.target.value})} placeholder="授权人（放行时必填）" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><button disabled={busy} onClick={async()=>{onBusy(true);try{const result=await createFulfillmentShipment(door.id,ship);notify(result.message);await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"发货失败"),true);}finally{onBusy(false);}}} className="col-span-2 h-9 bg-[#007AFF] text-sm text-white">确认出库发货</button></div></section></div><SimpleRecords title="发货记录" rows={door.shipments.map(item=>[item.status,item.carrier||"自送",item.vehicle_no||"-",item.authorized?`授权：${item.authorized_by}`:`收款 ¥${item.paid_amount}`,formatTime(item.created_at)])}/>{door.shipments.filter(item=>item.status!=="已签收").map(item=><div key={item.id} className="flex items-center justify-between border border-[#B8D8F8] bg-[#F4F9FF] p-3 text-sm"><span>{item.carrier||"自送"} · {item.vehicle_no||"无车牌/运单"} · 运输中</span><button disabled={busy} onClick={async()=>{const signedBy=window.prompt("请输入签收人")||"客户";onBusy(true);try{const result=await signFulfillmentShipment(item.id,{signed_by:signedBy,signed_at:"",remark:""});notify(result.message);await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"签收登记失败"),true);}finally{onBusy(false);}}} className="h-8 bg-[#248A3D] px-3 text-xs text-white">登记签收</button></div>)}<SimpleRecords title="计件工资草稿" rows={door.payroll_drafts.map(item=>[item.employee_uid||"未指定",item.work_name,`${item.quantity} × ¥${item.piece_rate}`,`¥${item.amount.toFixed(2)}`,item.status])}/></div>;}

function SimpleRecords({title,rows}:{title:string;rows:(string|number)[][]}){return <section><h3 className="mb-2 text-sm font-semibold">{title}</h3><div className="divide-y divide-[#E5E5EA] border border-[#D1D1D6]">{rows.length?rows.map((row,index)=><div key={index} className="grid gap-2 p-2 text-xs text-[#636366] md:grid-cols-5">{row.map((cell,i)=><span key={i} className={i===0?"font-semibold text-[#1C1C1E]":""}>{cell}</span>)}</div>):<div className="p-5 text-center text-xs text-[#8E8E93]">暂无记录</div>}</div></section>;}

function ExceptionBoard({ door, busy, notify, onBusy, onChanged }: WorkbenchProps) { const [form,setForm]=useState({category:"生产异常",title:"",detail:"",severity:"一般",owner_uid:""}); return <div className="space-y-4"><div className="grid gap-2 border border-[#D1D1D6] bg-[#F8F8FA] p-3 md:grid-cols-5"><select value={form.category} onChange={(e)=>setForm({...form,category:e.target.value})} className="h-9 border border-[#C7C7CC] px-2 text-sm"><option>缺料</option><option>外协延期</option><option>技术待确认</option><option>生产异常</option><option>质量返工</option><option>交期风险</option></select><input value={form.title} onChange={(e)=>setForm({...form,title:e.target.value})} placeholder="异常标题" className="h-9 border border-[#C7C7CC] px-2 text-sm md:col-span-2"/><input value={form.owner_uid} onChange={(e)=>setForm({...form,owner_uid:e.target.value})} placeholder="处理人" className="h-9 border border-[#C7C7CC] px-2 text-sm"/><button disabled={busy||!form.title.trim()} onClick={async()=>{onBusy(true);try{const result=await createFulfillmentException(door.id,form);notify(result.message);setForm({...form,title:"",detail:""});await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"异常登记失败"),true);}finally{onBusy(false);}}} className="h-9 bg-[#C62828] text-sm text-white disabled:opacity-50">登记异常</button><textarea value={form.detail} onChange={(e)=>setForm({...form,detail:e.target.value})} placeholder="异常详情" className="min-h-16 border border-[#C7C7CC] p-2 text-sm md:col-span-5"/></div>{door.exceptions.length===0?<Empty text="暂无异常记录"/>:<div className="divide-y divide-[#E5E5EA] border border-[#D1D1D6]">{door.exceptions.map(item=><div key={item.id} className="flex flex-wrap items-start gap-3 p-3"><Status text={item.status}/><div className="min-w-0 flex-1"><div className="text-sm font-semibold">{item.category} · {item.title}</div><div className="mt-1 text-xs text-[#636366]">{item.detail||"无详情"} · 处理人 {item.owner_uid||"未指定"}</div>{item.resolution&&<div className="mt-2 text-xs text-[#248A3D]">处理结果：{item.resolution}</div>}</div>{item.status!=="已解决"&&<button disabled={busy} onClick={async()=>{const resolution=window.prompt("请输入处理结果");if(!resolution)return;onBusy(true);try{const result=await resolveFulfillmentException(item.id,resolution);notify(result.message);await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"解决异常失败"),true);}finally{onBusy(false);}}} className="h-8 border border-[#C7C7CC] px-3 text-xs">标记解决</button>}</div>)}</div>}</div>; }

function ChangeButton({ door, notify, onBusy, onChanged }: {door:DoorUnitDetail;notify:(m:string,e?:boolean)=>void;onBusy:(v:boolean)=>void;onChanged:(d:DoorUnitDetail)=>Promise<void>}) { return <button onClick={async()=>{const reason=window.prompt("请输入生产变更原因");if(!reason)return;const impact=window.prompt("请输入对材料、采购、成本和交期的影响（可留空）")||"";onBusy(true);try{const result=await createFulfillmentChange(door.id,{reason,impact_note:impact});notify(result.message);await onChanged(result.door_unit);}catch(error){notify(apiMessage(error,"生产变更创建失败"),true);}finally{onBusy(false);}}} className="h-8 border border-[#248A3D] px-3 text-xs text-[#248A3D]">发起生产变更</button>; }

function Timeline({ door }: {door:DoorUnitDetail}) { return door.events.length===0?<Empty text="暂无履约事件"/>:<div className="divide-y divide-[#E5E5EA] border border-[#D1D1D6]">{door.events.map(item=><div key={item.id} className="grid gap-1 p-3 text-sm md:grid-cols-[150px_140px_minmax(0,1fr)_120px]"><span className="text-xs text-[#636366]">{formatTime(item.created_at)}</span><strong>{item.action}</strong><span>{item.detail}</span><span className="text-xs text-[#636366]">{item.operator_name}</span></div>)}</div>; }

function EditableTable({title,editable,onAdd,columns,children}:{title:string;editable:boolean;onAdd:()=>void;columns:string[];children:React.ReactNode}) { return <section><div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">{title}</h3>{editable&&<button onClick={onAdd} className="h-8 border border-[#007AFF] px-3 text-xs text-[#007AFF]">新增</button>}</div><div className="overflow-x-auto border border-[#D1D1D6]"><table className="w-full min-w-[800px] table-fixed text-sm"><thead className="bg-[#F2F2F7] text-left text-xs text-[#636366]"><tr>{columns.map(item=><th key={item} className="px-2 py-2 font-medium">{item}</th>)}</tr></thead><tbody>{children}</tbody></table></div></section>; }
function CellInput({disabled,value,onChange,type="text"}:{disabled:boolean;value:string|number;onChange:(value:string)=>void;type?:string}) { return <td className="px-2 py-2"><input disabled={disabled} type={type} value={value ?? ""} onChange={(event)=>onChange(event.target.value)} className="h-8 w-full border border-[#C7C7CC] px-2 text-sm disabled:border-transparent disabled:bg-transparent"/></td>; }
function updateAt<T>(items:T[],setter:(value:T[])=>void,index:number,patch:Partial<T>){const next=[...items];next[index]={...next[index],...patch};setter(next);}
function Status({text}:{text:string}) { const danger=/异常|返工|暂停/.test(text); const good=/完成|签收|确认|已入库/.test(text); return <span className={`inline-flex h-6 items-center px-2 text-xs ${danger?"bg-[#FFECEC] text-[#C62828]":good?"bg-[#EAF8ED] text-[#248A3D]":"bg-[#EDF3FF] text-[#315E9C]"}`}>{text||"未知"}</span>; }
function Empty({text,tall=false}:{text:string;tall?:boolean}) { return <div className={`flex items-center justify-center text-sm text-[#8E8E93] ${tall?"min-h-[480px]":"min-h-32"}`}>{text}</div>; }
function formatTime(value:string){return value?value.replace("T"," ").slice(0,16):"";}
function apiMessage(error:unknown,fallback:string){return (error as {userMessage?:string;message?:string})?.userMessage||(error as {message?:string})?.message||fallback;}
type WorkbenchProps={door:DoorUnitDetail;busy:boolean;notify:(message:string,error?:boolean)=>void;onBusy:(value:boolean)=>void;onChanged:(door:DoorUnitDetail)=>Promise<void>};
