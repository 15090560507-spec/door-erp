"use client";

import { useCallback, useEffect, useState } from "react";
import TopNav from "@/components/TopNav";
import ERPNextOrderDetail from "@/components/production/ERPNextOrderDetail";
import PendingReleaseList from "@/components/production/PendingReleaseList";
import ProductionFilters from "@/components/production/ProductionFilters";
import ProductionOrderList from "@/components/production/ProductionOrderList";
import { useAuth } from "@/hooks/useAuth";
import {
  getERPNextBridgeStatus,
  getPendingProductionTasks,
  getProductionOrder,
  getProductionOrders,
} from "@/lib/productionApi";
import type { ERPNextBridgeStatus, PendingProductionTask, ProductionOrder, ProductionOrderFilters } from "@/lib/productionTypes";

const emptyFilters: ProductionOrderFilters = { q: "", stage: "", status: "", owner: "", shortage: "", due_from: "", due_to: "" };

export default function ProductionPage() {
  const { setModule } = useAuth();
  const [orders, setOrders] = useState<ProductionOrder[]>([]);
  const [pendingTasks, setPendingTasks] = useState<PendingProductionTask[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<ProductionOrder | null>(null);
  const [filters, setFilters] = useState<ProductionOrderFilters>(emptyFilters);
  const [bridge, setBridge] = useState<ERPNextBridgeStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);

  const notify = useCallback((message: string, error = false) => setNotice({ message, error }), []);
  const load = useCallback(async (nextFilters = filters) => {
    const [nextOrders, nextPending, nextBridge] = await Promise.all([
      getProductionOrders(nextFilters), getPendingProductionTasks(), getERPNextBridgeStatus(),
    ]);
    setOrders(nextOrders); setPendingTasks(nextPending); setBridge(nextBridge);
  }, [filters]);

  useEffect(() => { setModule("生产管理"); }, [setModule]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load().catch((error) => !cancelled && notify(apiMessage(error, "生产订单加载失败"), true)).finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [load, notify]);
  useEffect(() => {
    if (!selectedId) { setSelectedOrder(null); return; }
    getProductionOrder(selectedId).then(setSelectedOrder).catch((error) => notify(apiMessage(error, "订单详情加载失败"), true));
  }, [selectedId, notify]);

  const refresh = async () => {
    try {
      await load();
      if (selectedId) setSelectedOrder(await getProductionOrder(selectedId));
    } catch (error) { notify(apiMessage(error, "刷新失败"), true); }
  };
  const applyFilters = (next: ProductionOrderFilters) => { setFilters({ ...next }); setSelectedId(null); };

  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]">
    <TopNav />
    <main className="mx-auto max-w-[1600px] space-y-5 px-4 py-5 sm:px-6">
      <header className="flex flex-wrap items-end gap-4">
        <div className="flex-1"><h1 className="text-xl font-semibold">生产管理</h1><p className="mt-1 text-sm text-[#636366]">销售在 Door ERP 下达冻结订单；技术、采购、仓储、生产、质检和发货在 ERPNext 办理。</p></div>
        <button onClick={() => void refresh()} className="h-9 border border-[#C7C7CC] bg-white px-4 text-sm">刷新</button>
      </header>

      <section className={`border p-4 text-sm ${bridge?.configured && bridge?.enabled ? "border-[#B7E0BF] bg-[#F2FFF3]" : "border-[#F2D18B] bg-[#FFF9EB]"}`}>
        <strong>ERPNext 集成：</strong>{bridge?.message || "正在读取配置"}
        {bridge?.public_url && <a href={bridge.public_url} target="_blank" rel="noreferrer" className="ml-3 text-[#007AFF] hover:underline">打开 ERPNext</a>}
      </section>

      <PendingReleaseList tasks={pendingTasks} canRelease onReleased={() => void refresh()} />

      <section className="border border-[#E5E5EA] bg-white p-5"><h2 className="mb-1 font-semibold">已冻结生产订单</h2><p className="mb-4 text-sm text-[#636366]">这里只跟踪 Door ERP 下达和 ERPNext 同步；生产单据以 ERPNext 为准。</p><ProductionFilters value={filters} onChange={setFilters} onApply={applyFilters} />
        {loading ? <div className="py-12 text-center text-sm text-[#8E8E93]">正在加载生产订单...</div> : <ProductionOrderList orders={orders} selectedId={selectedId} onSelect={setSelectedId} />}
      </section>
      {selectedOrder && <ERPNextOrderDetail order={selectedOrder} bridge={bridge} notify={notify} onChanged={() => void refresh()} />}
    </main>
    {notice && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={() => setNotice(null)}><div className="w-full max-w-sm border border-[#D1D1D6] bg-white p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}><h3 className="font-semibold">{notice.error ? "操作失败" : "操作成功"}</h3><p className={`mt-3 text-sm ${notice.error ? "text-[#FF3B30]" : "text-[#248A3D]"}`}>{notice.message}</p><div className="mt-5 text-right"><button onClick={() => setNotice(null)} className="h-9 bg-[#007AFF] px-5 text-sm text-white">知道了</button></div></div></div>}
  </div>;
}

function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
