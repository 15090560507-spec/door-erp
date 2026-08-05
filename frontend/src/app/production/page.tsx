"use client";

import { useCallback, useEffect, useState } from "react";
import TopNav from "@/components/TopNav";
import PendingReleaseList from "@/components/production/PendingReleaseList";
import ProductionDashboard from "@/components/production/ProductionDashboard";
import ProductionFilters from "@/components/production/ProductionFilters";
import ProductionMaterials from "@/components/production/ProductionMaterials";
import ProductionOrderDetail from "@/components/production/ProductionOrderDetail";
import ProductionOrderList from "@/components/production/ProductionOrderList";
import ProductionPurchasing from "@/components/production/ProductionPurchasing";
import ProductionShipping from "@/components/production/ProductionShipping";
import ProductionWarehouse from "@/components/production/ProductionWarehouse";
import { useAuth } from "@/hooks/useAuth";
import {
  getPendingProductionTasks,
  getProductionDashboard,
  getProductionOrder,
  getProductionOrders,
} from "@/lib/productionApi";
import type {
  PendingProductionTask,
  ProductionOrder,
  ProductionOrderFilters,
} from "@/lib/productionTypes";

type View = "dashboard" | "orders" | "bom" | "schedule" | "cutting" | "purchasing" | "warehouse" | "quality" | "shipping";

const views: Array<{ key: View; label: string }> = [
  { key: "dashboard", label: "生产总览" },
  { key: "orders", label: "生产订单" },
  { key: "bom", label: "BOM 与备料" },
  { key: "schedule", label: "生产排单" },
  { key: "cutting", label: "综合下料" },
  { key: "purchasing", label: "采购" },
  { key: "warehouse", label: "仓储" },
  { key: "quality", label: "质检与成品" },
  { key: "shipping", label: "发货" },
];

const allProductionPermissions = [
  "production.sales", "production.technical", "production.purchase", "production.warehouse",
  "production.schedule", "production.cutting", "production.worker", "production.quality",
  "production.shipping", "production.manager",
];

const emptyFilters: ProductionOrderFilters = {
  q: "", stage: "", status: "", owner: "", shortage: "", due_from: "", due_to: "",
};

export default function ProductionPage() {
  const { setModule } = useAuth();
  const permissions = allProductionPermissions;
  const [view, setView] = useState<View>("dashboard");
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [orders, setOrders] = useState<ProductionOrder[]>([]);
  const [pendingTasks, setPendingTasks] = useState<PendingProductionTask[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<ProductionOrder | null>(null);
  const [draftFilters, setDraftFilters] = useState<ProductionOrderFilters>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<ProductionOrderFilters>(emptyFilters);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);

  const notify = useCallback((message: string, error = false) => setNotice({ message, error }), []);
  const loadSummary = useCallback(async (filters: ProductionOrderFilters) => {
    const [nextCounts, nextOrders, nextPending] = await Promise.all([
      getProductionDashboard(), getProductionOrders(filters), getPendingProductionTasks(),
    ]);
    setCounts(nextCounts);
    setOrders(nextOrders);
    setPendingTasks(nextPending);
  }, []);

  useEffect(() => {
    setModule("生产履约");
    const requestedOrder = Number(new URLSearchParams(window.location.search).get("order") || 0);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (requestedOrder) { setSelectedId(requestedOrder); setView("orders"); }
  }, [setModule]);

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    loadSummary(appliedFilters).catch((error) => {
      if (!cancelled) notify(apiMessage(error, "生产履约数据加载失败"), true);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [appliedFilters, loadSummary, notify]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!selectedId) { setSelectedOrder(null); return; }
    let cancelled = false;
    getProductionOrder(selectedId)
      .then((order) => { if (!cancelled) setSelectedOrder(order); })
      .catch((error) => { if (!cancelled) notify(apiMessage(error, "生产订单加载失败"), true); });
    return () => { cancelled = true; };
  }, [notify, selectedId]);

  const refresh = async () => {
    try {
      await loadSummary(appliedFilters);
      if (selectedId) setSelectedOrder(await getProductionOrder(selectedId));
    } catch (error) { notify(apiMessage(error, "刷新失败"), true); }
  };

  const applyFilters = (filters: ProductionOrderFilters) => {
    setAppliedFilters({ ...filters });
    setSelectedId(null);
  };

  const filterFromDashboard = (key: string) => {
    const today = new Date();
    const filters = { ...emptyFilters };
    if (key === "缺料") filters.shortage = "缺料";
    else if (["下料", "生产", "质检", "入库", "发货", "完成"].includes(key)) filters.stage = key;
    else if (key === "即将到期") {
      filters.due_from = dateValue(today);
      const end = new Date(today); end.setDate(end.getDate() + 3); filters.due_to = dateValue(end);
    } else if (key === "已逾期") {
      const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1); filters.due_to = dateValue(yesterday);
    }
    setDraftFilters(filters);
    setAppliedFilters(filters);
    setView("orders");
  };

  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]">
    <TopNav />
    <main className="mx-auto max-w-[1600px] space-y-5 px-4 py-5 sm:px-6">
      <header className="flex flex-wrap items-end gap-4">
        <div className="flex-1"><h1 className="text-xl font-semibold">生产履约</h1><p className="mt-1 text-sm text-[#636366]">生产订单发布后，依次完成 BOM、备料、排单、下料、生产、质检、入库和发货。</p></div>
        <button onClick={() => void refresh()} className="h-9 border border-[#C7C7CC] bg-white px-4 text-sm">刷新</button>
      </header>

      <nav className="flex overflow-x-auto border border-[#E5E5EA] bg-white">
        {views.map((item) => <button key={item.key} onClick={() => setView(item.key)} className={`h-11 whitespace-nowrap border-r border-[#E5E5EA] px-5 text-sm ${view === item.key ? 'bg-[#007AFF] font-medium text-white' : 'text-[#48484A] hover:bg-[#F7F7F9]'}`}>{item.label}</button>)}
      </nav>

      {view === "dashboard" && <>
        <ProductionDashboard counts={counts} onFilter={filterFromDashboard} />
        <PendingReleaseList tasks={pendingTasks} canRelease onReleased={() => void refresh()} />
        <section className="border border-[#E5E5EA] bg-white p-5"><h2 className="mb-4 font-semibold">最近生产订单</h2><ProductionOrderList orders={orders.slice(0, 8)} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setView("orders"); }} /></section>
      </>}

      {view === "orders" && <div className="space-y-5">
        <PendingReleaseList tasks={pendingTasks} canRelease onReleased={() => void refresh()} />
        <ProductionFilters value={draftFilters} onChange={setDraftFilters} onApply={applyFilters} />
        {loading ? <div className="border border-[#E5E5EA] bg-white p-12 text-center text-sm text-[#8E8E93]">正在加载生产订单...</div> : <ProductionOrderList orders={orders} selectedId={selectedId} onSelect={setSelectedId} />}
        {selectedOrder && <ProductionOrderDetail order={selectedOrder} permissions={permissions} notify={notify} onChanged={() => void refresh()} />}
      </div>}

      {view === "bom" && <div className="space-y-5"><ProductionMaterials canEdit notify={notify} /><OrderWorkbench title="BOM 与备料订单" description="建立物料资料后，在订单详情中手工录入并发布 BOM；系统会自动生成需求和预留库存。" orders={orders.filter((order) => ['BOM准备', '备料'].includes(order.stage))} selectedId={selectedId} onSelect={setSelectedId} selectedOrder={selectedOrder} permissions={permissions} notify={notify} refresh={refresh} /></div>}
      {view === "schedule" && <OrderWorkbench title="生产排单" description="安排计划开始、完成日期、生产人和负责人；缺料排单需要明确确认。" orders={orders.filter((order) => !['已完成', '已作废', '已撤回'].includes(order.status))} selectedId={selectedId} onSelect={setSelectedId} selectedOrder={selectedOrder} permissions={permissions} notify={notify} refresh={refresh} />}
      {view === "cutting" && <OrderWorkbench title="综合下料" description="BOM 已发布且物料备齐后，可生成综合下料单并记录实际下料。" orders={orders.filter((order) => ['备料', '下料', '生产'].includes(order.stage))} selectedId={selectedId} onSelect={setSelectedId} selectedOrder={selectedOrder} permissions={permissions} notify={notify} refresh={refresh} />}
      {view === "purchasing" && <ProductionPurchasing notify={notify} />}
      {view === "warehouse" && <ProductionWarehouse notify={notify} />}
      {view === "quality" && <OrderWorkbench title="质检与成品" description="跟踪生产工序、成品质检和成品入库。" orders={orders.filter((order) => ['生产', '质检', '入库'].includes(order.stage))} selectedId={selectedId} onSelect={setSelectedId} selectedOrder={selectedOrder} permissions={permissions} notify={notify} refresh={refresh} />}
      {view === "shipping" && <ProductionShipping canEdit notify={notify} />}
    </main>
    {notice && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={() => setNotice(null)}><div className="w-full max-w-sm border border-[#D1D1D6] bg-white p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}><h3 className="font-semibold">{notice.error ? "操作失败" : "操作成功"}</h3><p className={`mt-3 text-sm ${notice.error ? 'text-[#FF3B30]' : 'text-[#248A3D]'}`}>{notice.message}</p><div className="mt-5 text-right"><button onClick={() => setNotice(null)} className="h-9 bg-[#007AFF] px-5 text-sm text-white">知道了</button></div></div></div>}
  </div>;
}

function OrderWorkbench({ title, description, orders, selectedId, onSelect, selectedOrder, permissions, notify, refresh }: {
  title: string; description: string; orders: ProductionOrder[]; selectedId: number | null;
  onSelect: (id: number) => void; selectedOrder: ProductionOrder | null; permissions: string[];
  notify: (message: string, error?: boolean) => void; refresh: () => Promise<void>;
}) {
  return <div className="space-y-5"><section className="border border-[#E5E5EA] bg-white p-5"><h2 className="font-semibold">{title}</h2><p className="mt-1 text-sm text-[#636366]">{description}</p></section><ProductionOrderList orders={orders} selectedId={selectedId} onSelect={onSelect} />{selectedOrder && <ProductionOrderDetail order={selectedOrder} permissions={permissions} notify={notify} onChanged={() => void refresh()} />}</div>;
}

function dateValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
