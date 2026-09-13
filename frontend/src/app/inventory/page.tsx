"use client";

import { Boxes, ClipboardCheck, RefreshCw, Settings2, Warehouse } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import InventoryWorkspace from "@/components/inventory/InventoryWorkspace";
import WarehouseSettings from "@/components/inventory/WarehouseSettings";
import InlineError from "@/components/workspace/InlineError";
import MetricStrip from "@/components/workspace/MetricStrip";
import WorkspaceHeader from "@/components/workspace/WorkspaceHeader";
import { getInventoryBalances, getPendingMaterialIssues, getPurchaseOrders, getPurchaseReceipts } from "@/lib/inventoryApi";

type InventorySummary = { stocked: number; lowStock: number; pendingIssue: number; pendingInspection: number; inTransit: number };
const EMPTY_SUMMARY: InventorySummary = { stocked: 0, lowStock: 0, pendingIssue: 0, pendingInspection: 0, inTransit: 0 };

export default function InventoryPage() {
  const [settings, setSettings] = useState(false);
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const [summary, setSummary] = useState<InventorySummary>(EMPTY_SUMMARY);
  const [summaryError, setSummaryError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const loadSummary = useCallback(async () => {
    setRefreshing(true);
    try {
      const [balances, pendingIssues, pendingReceipts, purchaseOrders] = await Promise.all([
        getInventoryBalances(), getPendingMaterialIssues(), getPurchaseReceipts("待检"), getPurchaseOrders(),
      ]);
      setSummary({
        stocked: balances.filter((item) => Number(item.on_hand) > 0).length,
        lowStock: balances.filter((item) => Number(item.available) < Number(item.minimum_stock || 0)).length,
        pendingIssue: pendingIssues.length,
        pendingInspection: pendingReceipts.length,
        inTransit: purchaseOrders.filter((item) => item.status === "已下单" || item.status === "部分到货").length,
      });
      setSummaryError("");
    } catch (error) {
      setSummaryError(errorMessage(error, "库存指标加载失败"));
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
      title={settings ? "仓库与库位" : "库存管理"}
      description={settings ? "维护全厂公共仓库和库位，不按客户或订单重复建仓。" : "全厂共享库存，统一处理待检、领退料、调拨、报废和库存流水。"}
      context={<><Warehouse size={14} />经营管理 / 全厂库存</>}
      actions={<><button type="button" className="ui-button ui-button--secondary" disabled={refreshing} onClick={() => void loadSummary()}><RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />刷新指标</button><button type="button" onClick={() => setSettings((value) => !value)} className="ui-button ui-button--primary"><Settings2 size={15} />{settings ? "返回库存业务" : "仓库与库位"}</button></>}
    />
    {!settings && <MetricStrip items={[
      { key: "stocked", label: "有库存物料", value: summary.stocked, detail: "当前现存量大于零", icon: <Boxes size={16} />, tone: "blue" },
      { key: "low", label: "低于安全库存", value: summary.lowStock, detail: "已建账库存低于安全线", icon: <Warehouse size={16} />, tone: summary.lowStock ? "red" : "green" },
      { key: "issue", label: "待领料", value: summary.pendingIssue, detail: "已预留、等待仓库发料", icon: <ClipboardCheck size={16} />, tone: summary.pendingIssue ? "amber" : "neutral" },
      { key: "inspection", label: "采购待检", value: summary.pendingInspection, detail: "检验通过后转现存库存", icon: <ClipboardCheck size={16} />, tone: summary.pendingInspection ? "amber" : "neutral" },
      { key: "transit", label: "在途采购单", value: summary.inTransit, detail: "已下单或部分到货", icon: <Boxes size={16} />, tone: "violet" },
    ]} />}
    {summaryError && <InlineError title="库存指标暂不可用" message={summaryError} onRetry={() => void loadSummary()} />}
    {notice && (notice.error ? <InlineError message={notice.message} onDismiss={() => setNotice(null)} /> : <button type="button" onClick={() => setNotice(null)} className="workspace-success">{notice.message}</button>)}
    {settings ? <WarehouseSettings notify={notify} /> : <InventoryWorkspace notify={notify} />}
  </main></div>;
}

function errorMessage(error: unknown, fallback: string) {
  return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback;
}
