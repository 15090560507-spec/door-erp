"use client";

import { Boxes, Database, Factory, Link2, RefreshCw, Workflow } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import MasterDataWorkspace from "@/components/inventory/MasterDataWorkspace";
import InlineError from "@/components/workspace/InlineError";
import MetricStrip from "@/components/workspace/MetricStrip";
import WorkspaceHeader from "@/components/workspace/WorkspaceHeader";
import { getInventoryBomRules, getInventoryMaterials, getInventorySupplierItems, getInventorySuppliers } from "@/lib/inventoryApi";

type MasterSummary = { materials: number; purchasable: number; suppliers: number; relations: number; rules: number };
const EMPTY_SUMMARY: MasterSummary = { materials: 0, purchasable: 0, suppliers: 0, relations: 0, rules: 0 };

export default function MasterDataPage() {
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const [summary, setSummary] = useState<MasterSummary>(EMPTY_SUMMARY);
  const [summaryError, setSummaryError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const loadSummary = useCallback(async () => {
    setRefreshing(true);
    try {
      const [materials, suppliers, relations, rules] = await Promise.all([
        getInventoryMaterials({ include_inactive: true }),
        getInventorySuppliers({ include_inactive: true }),
        getInventorySupplierItems(),
        getInventoryBomRules({ include_inactive: true }),
      ]);
      setSummary({
        materials: materials.filter((item) => Boolean(item.is_active)).length,
        purchasable: materials.filter((item) => Boolean(item.is_active) && Boolean(item.can_purchase)).length,
        suppliers: suppliers.filter((item) => Boolean(item.is_active)).length,
        relations: relations.filter((item) => Boolean(item.is_active)).length,
        rules: rules.filter((item) => Boolean(item.is_active)).length,
      });
      setSummaryError("");
    } catch (error) {
      setSummaryError(errorMessage(error, "基础资料指标加载失败"));
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
      title="基础资料"
      description="一个内部商品主档关联多个供应商供货关系，BOM 引用内部商品，采购时再选择具体供应商。"
      context={<><Database size={14} />经营管理 / 数据底座</>}
      actions={<button type="button" className="ui-button ui-button--secondary" disabled={refreshing} onClick={() => void loadSummary()}><RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />刷新指标</button>}
    />
    <MetricStrip items={[
      { key: "materials", label: "启用商品", value: summary.materials, detail: "当前可用于 BOM 的内部商品", icon: <Boxes size={16} />, tone: "blue" },
      { key: "purchasable", label: "可采购商品", value: summary.purchasable, detail: "允许进入采购需求池", icon: <Factory size={16} />, tone: "violet" },
      { key: "suppliers", label: "合作供应商", value: summary.suppliers, detail: "当前启用的供应商", icon: <Factory size={16} />, tone: "green" },
      { key: "relations", label: "有效供货关系", value: summary.relations, detail: "供应商与商品的有效关联", icon: <Link2 size={16} />, tone: "amber" },
      { key: "rules", label: "启用 BOM 规则", value: summary.rules, detail: "生成草稿 BOM 时自动匹配", icon: <Workflow size={16} />, tone: "blue" },
    ]} />
    {summaryError && <InlineError title="基础资料指标暂不可用" message={summaryError} onRetry={() => void loadSummary()} />}
    {notice && (notice.error ? <InlineError message={notice.message} onDismiss={() => setNotice(null)} /> : <button type="button" onClick={() => setNotice(null)} className="workspace-success">{notice.message}</button>)}
    <MasterDataWorkspace notify={notify} />
  </main></div>;
}

function errorMessage(error: unknown, fallback: string) {
  return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback;
}
