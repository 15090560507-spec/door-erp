"use client";

import { ClipboardList, PackageCheck, RefreshCw, ShoppingCart, Truck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import PurchasingCenter from "@/components/inventory/PurchasingCenter";
import SupplyRequirements from "@/components/inventory/SupplyRequirements";
import InlineError from "@/components/workspace/InlineError";
import MetricStrip from "@/components/workspace/MetricStrip";
import WorkspaceHeader from "@/components/workspace/WorkspaceHeader";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";
import { getPurchaseOrders, getPurchaseReceipts, getPurchaseShortages } from "@/lib/inventoryApi";

type PurchasingSummary = {
  shortageCount: number;
  draftCount: number;
  transitCount: number;
  pendingInspectionCount: number;
};

const EMPTY_SUMMARY: PurchasingSummary = { shortageCount: 0, draftCount: 0, transitCount: 0, pendingInspectionCount: 0 };

export default function PurchasingPage() {
  const [tab, setTab] = useState<"requirements" | "orders">("requirements");
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const [summary, setSummary] = useState<PurchasingSummary>(EMPTY_SUMMARY);
  const [summaryError, setSummaryError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const loadSummary = useCallback(async () => {
    setRefreshing(true);
    try {
      const [shortages, orders, pendingReceipts] = await Promise.all([
        getPurchaseShortages(), getPurchaseOrders(), getPurchaseReceipts("待检"),
      ]);
      setSummary({
        shortageCount: shortages.length,
        draftCount: orders.filter((item) => item.status === "草稿").length,
        transitCount: orders.filter((item) => ["已下单", "部分到货"].includes(item.status)).length,
        pendingInspectionCount: pendingReceipts.length,
      });
      setSummaryError("");
    } catch (error) {
      setSummaryError(errorMessage(error, "采购指标加载失败"));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadSummary(), 0);
    return () => window.clearTimeout(timer);
  }, [loadSummary]);
  const notify = useCallback((message: string, error = false) => {
    setNotice({ message, error });
    if (!error) void loadSummary();
  }, [loadSummary]);

  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]"><main className="workspace-page workspace-page--wide space-y-4">
    <WorkspaceHeader
      title="采购管理"
      description="统一处理生产缺料、合并采购、供应商到货和来料待检，所有进度由采购与收货事件自动汇总。"
      context={<><ShoppingCart size={14} />经营管理 / 供应协同</>}
      actions={<button type="button" className="ui-button ui-button--secondary" disabled={refreshing} onClick={() => void loadSummary()}><RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />刷新指标</button>}
    />
    <MetricStrip items={[
      { key: "shortage", label: "待采购缺口", value: summary.shortageCount, detail: "尚未被库存或采购覆盖", icon: <ClipboardList size={16} />, tone: summary.shortageCount ? "red" : "green" },
      { key: "draft", label: "采购单草稿", value: summary.draftCount, detail: "等待确认下单", icon: <ShoppingCart size={16} />, tone: "amber" },
      { key: "transit", label: "采购在途", value: summary.transitCount, detail: "已下单或部分到货", icon: <Truck size={16} />, tone: "blue" },
      { key: "inspection", label: "到货待检", value: summary.pendingInspectionCount, detail: "检验后才进入可用库存", icon: <PackageCheck size={16} />, tone: summary.pendingInspectionCount ? "amber" : "neutral" },
    ]} />
    {summaryError && <InlineError title="采购指标暂不可用" message={summaryError} onRetry={() => void loadSummary()} />}
    {notice && (notice.error ? <InlineError message={notice.message} onDismiss={() => setNotice(null)} /> : <button type="button" onClick={() => setNotice(null)} className="workspace-success">{notice.message}</button>)}
    <WorkspaceTabs items={[{ key: "requirements", label: "采购需求池" }, { key: "orders", label: "采购订单与到货" }] as const} value={tab} onChange={setTab} ariaLabel="采购管理视图" />
    {tab === "requirements" ? <SupplyRequirements notify={notify} /> : <PurchasingCenter notify={notify} />}
  </main></div>;
}

function errorMessage(error: unknown, fallback: string) {
  return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback;
}
