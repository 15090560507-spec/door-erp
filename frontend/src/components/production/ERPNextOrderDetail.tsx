"use client";

import { useState } from "react";
import { downloadProductionFile, syncProductionOrderToERPNext } from "@/lib/productionApi";
import type { ERPNextBridgeStatus, ProductionOrder } from "@/lib/productionTypes";

export default function ERPNextOrderDetail({
  order,
  bridge,
  notify,
  onChanged,
}: {
  order: ProductionOrder;
  bridge: ERPNextBridgeStatus | null;
  notify: (message: string, error?: boolean) => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const sync = order.erpnext_sync;
  const status = sync?.status || order.erpnext_sync_status || "未同步";
  const salesOrder = sync?.erpnext_sales_order || order.erpnext_sales_order;
  const url = sync?.erpnext_url || order.erpnext_url;
  const error = sync?.last_error || order.erpnext_last_error;

  const runSync = async () => {
    setBusy(true);
    try {
      const result = await syncProductionOrderToERPNext(order.id);
      notify(result.message, result.order.erpnext_sync?.status !== "已同步");
      onChanged();
    } catch (cause) {
      notify((cause as { userMessage?: string })?.userMessage || "ERPNext 同步失败", true);
    } finally {
      setBusy(false);
    }
  };

  return <section className="border border-[#D1D1D6] bg-white">
    <header className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] px-5 py-4">
      <div className="min-w-56 flex-1">
        <div className="text-xs text-[#8E8E93]">Door ERP 冻结生产订单</div>
        <h2 className="text-lg font-semibold">{order.order_no} · {order.customer}</h2>
        <p className="mt-1 text-xs text-[#636366]">{order.project || "无项目名称"} · 要求交期：{order.due_date || "未填写"}</p>
      </div>
      <button disabled={busy} onClick={() => void downloadProductionFile(`/production/orders/${order.id}/approved-dxf`, `${order.order_no}_终审冻结版.dxf`)} className="h-9 border border-[#C7C7CC] px-3 text-sm disabled:opacity-50">下载冻结 DXF</button>
      {url && <a href={url} target="_blank" rel="noreferrer" className="inline-flex h-9 items-center bg-[#007AFF] px-4 text-sm text-white">进入 ERPNext 办理</a>}
    </header>

    <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section>
        <h3 className="font-semibold">同步状态</h3>
        <div className={`mt-3 border p-4 text-sm ${status === "已同步" ? "border-[#B7E0BF] bg-[#F2FFF3]" : status === "同步失败" ? "border-[#FFD0CC] bg-[#FFF5F4]" : "border-[#F2D18B] bg-[#FFF9EB]"}`}>
          <div className="font-medium">{status}</div>
          {salesOrder && <div className="mt-2 text-[#48484A]">ERPNext 销售订单：<strong>{salesOrder}</strong></div>}
          {sync?.erpnext_item_code && <div className="mt-1 text-[#636366]">订单专用成品：{sync.erpnext_item_code}</div>}
          {sync?.last_synced_at && <div className="mt-1 text-xs text-[#8E8E93]">最近同步：{sync.last_synced_at.replace("T", " ").slice(0, 16)}</div>}
          {error && <div className="mt-3 break-words text-[#FF3B30]">{error}</div>}
        </div>
        {status !== "已同步" && <button disabled={busy || !bridge?.configured || !bridge?.enabled} onClick={() => void runSync()} className="mt-4 h-10 bg-[#248A3D] px-5 text-sm text-white disabled:cursor-not-allowed disabled:opacity-40">{busy ? "正在同步..." : status === "同步失败" ? "重试同步 ERPNext" : "同步至 ERPNext"}</button>}
        {(!bridge?.configured || !bridge?.enabled) && <p className="mt-3 text-xs text-[#C76E00]">{bridge?.message || "正在读取 ERPNext 配置"}。请由服务器管理员在 `.env` 配置后端 API 凭证。</p>}
      </section>
      <section className="border-l-0 border-[#E5E5EA] lg:border-l lg:pl-5">
        <h3 className="font-semibold">业务交接</h3>
        <ol className="mt-3 space-y-2 text-sm leading-6 text-[#48484A]">
          <li>1. 销售在 Door ERP 完成终审、冻结资料并同步订单。</li>
          <li>2. 技术在 ERPNext 建立并审核 BOM。</li>
          <li>3. 采购、仓储、生产、质检和发货均在 ERPNext 办理。</li>
          <li>4. Door ERP 保留图纸、报价和订单来源，不重复维护生产台账。</li>
        </ol>
      </section>
    </div>
  </section>;
}
