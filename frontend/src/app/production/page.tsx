"use client";

import { useCallback, useEffect, useState } from "react";
import TopNav from "@/components/TopNav";
import ProductionDashboard from "@/components/production/ProductionDashboard";
import ProductionMaterials from "@/components/production/ProductionMaterials";
import ProductionOrderDetail from "@/components/production/ProductionOrderDetail";
import ProductionOrderList from "@/components/production/ProductionOrderList";
import ProductionShipping from "@/components/production/ProductionShipping";
import ProductionSupply from "@/components/production/ProductionSupply";
import { useAuth } from "@/hooks/useAuth";
import { getProductionDashboard, getProductionOrder, getProductionOrders } from "@/lib/productionApi";
import type { ProductionOrder } from "@/lib/productionTypes";

type View = "dashboard" | "orders" | "materials" | "supply" | "shipping";

const views: Array<{ key: View; label: string }> = [
  { key: "dashboard", label: "生产总览" },
  { key: "orders", label: "生产订单" },
  { key: "materials", label: "生产物料" },
  { key: "supply", label: "采购与库存" },
  { key: "shipping", label: "成品与发货" },
];

export default function ProductionPage() {
  const { user, setModule } = useAuth();
  const permissions = user?.permissions || [];
  const [view, setView] = useState<View>("dashboard");
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [orders, setOrders] = useState<ProductionOrder[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<ProductionOrder | null>(null);
  const [stage, setStage] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);

  const notify = useCallback((message: string, error = false) => setNotice({ message, error }), []);
  const loadSummary = useCallback(async () => {
    const [nextCounts, nextOrders] = await Promise.all([
      getProductionDashboard(),
      getProductionOrders({ stage, q: query }),
    ]);
    setCounts(nextCounts);
    setOrders(nextOrders);
  }, [query, stage]);

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
    loadSummary().catch((error) => {
      if (!cancelled) notify(apiMessage(error, "生产履约数据加载失败"), true);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [loadSummary, notify]);

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
      await loadSummary();
      if (selectedId) setSelectedOrder(await getProductionOrder(selectedId));
    } catch (error) { notify(apiMessage(error, "刷新失败"), true); }
  };

  if (!permissions.length) {
    return <><TopNav /><main className="mx-auto max-w-7xl px-6 py-12"><div className="border border-[#FFD1D1] bg-white p-8 text-center text-[#FF3B30]">当前账号尚未分配生产履约权限，请联系超级管理员。</div></main></>;
  }

  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]">
    <TopNav />
    <main className="mx-auto max-w-7xl space-y-5 px-4 py-5 sm:px-6">
      <header className="flex flex-wrap items-end gap-4">
        <div className="flex-1"><h1 className="text-xl font-semibold">生产履约</h1><p className="mt-1 text-sm text-[#636366]">从已确认订单开始，跟踪 BOM、下料、生产、质检、入库和发货。</p></div>
        <button onClick={() => void refresh()} className="h-9 border border-[#C7C7CC] bg-white px-4 text-sm">刷新</button>
      </header>

      <nav className="flex overflow-x-auto border border-[#E5E5EA] bg-white">
        {views.map((item) => <button key={item.key} onClick={() => setView(item.key)} className={`h-11 whitespace-nowrap border-r border-[#E5E5EA] px-5 text-sm ${view === item.key ? 'bg-[#007AFF] font-medium text-white' : 'text-[#48484A] hover:bg-[#F7F7F9]'}`}>{item.label}</button>)}
      </nav>

      {view === "dashboard" && <><ProductionDashboard counts={counts} onFilter={(nextStage) => { setStage(nextStage === '完成' ? '完成' : nextStage); setView('orders'); }} /><section className="border border-[#E5E5EA] bg-white p-5"><h2 className="mb-4 font-semibold">最近生产订单</h2><ProductionOrderList orders={orders.slice(0, 8)} selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setView('orders'); }} /></section></>}

      {view === "orders" && <div className="space-y-5">
        <section className="flex flex-wrap gap-3 border border-[#E5E5EA] bg-white p-4">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索生产单号、客户、项目" className="h-10 min-w-64 flex-1 border border-[#C7C7CC] px-3 text-sm" />
          <select value={stage} onChange={(event) => setStage(event.target.value)} className="h-10 border border-[#C7C7CC] bg-white px-3 text-sm"><option value="">全部阶段</option>{['BOM准备', '备料', '下料', '生产', '质检', '入库', '发货', '完成'].map((item) => <option key={item}>{item}</option>)}</select>
          <button onClick={() => void loadSummary()} className="h-10 bg-[#007AFF] px-5 text-sm text-white">查询</button>
        </section>
        {loading ? <div className="border border-[#E5E5EA] bg-white p-12 text-center text-sm text-[#8E8E93]">正在加载生产订单...</div> : <ProductionOrderList orders={orders} selectedId={selectedId} onSelect={setSelectedId} />}
        {selectedOrder && <ProductionOrderDetail order={selectedOrder} permissions={permissions} notify={notify} onChanged={() => void refresh()} />}
      </div>}

      {view === "materials" && <ProductionMaterials canEdit={permissions.some((item) => ['production.technical', 'production.warehouse', 'production.purchase'].includes(item))} notify={notify} />}
      {view === "supply" && <ProductionSupply permissions={permissions} notify={notify} />}
      {view === "shipping" && <ProductionShipping canEdit={permissions.includes('production.shipping')} notify={notify} />}
    </main>
    {notice && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={() => setNotice(null)}><div className="w-full max-w-sm border border-[#D1D1D6] bg-white p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}><h3 className="font-semibold">{notice.error ? '操作失败' : '操作成功'}</h3><p className={`mt-3 text-sm ${notice.error ? 'text-[#FF3B30]' : 'text-[#248A3D]'}`}>{notice.message}</p><div className="mt-5 text-right"><button onClick={() => setNotice(null)} className="h-9 bg-[#007AFF] px-5 text-sm text-white">知道了</button></div></div></div>}
  </div>;
}

function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string })?.userMessage || fallback; }
