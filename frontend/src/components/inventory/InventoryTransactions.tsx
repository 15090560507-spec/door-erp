"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getInventoryMaterials, getInventoryTransactions } from "@/lib/inventoryApi";
import type { InventoryMaterial, InventoryTransaction } from "@/lib/inventoryTypes";

export default function InventoryTransactions({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([]);
  const [materialId, setMaterialId] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextMaterials, nextTransactions] = await Promise.all([getInventoryMaterials(), getInventoryTransactions({ material_id: materialId ? Number(materialId) : undefined, limit: 500 })]);
      setMaterials(nextMaterials); setTransactions(nextTransactions);
    } catch (error) { notify(apiMessage(error, "库存流水加载失败"), true); }
    finally { setLoading(false); }
  }, [materialId, notify]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  const inbound = useMemo(() => transactions.filter((item) => item.quantity > 0).reduce((sum, item) => sum + item.quantity, 0), [transactions]);
  const outbound = useMemo(() => transactions.filter((item) => item.quantity < 0).reduce((sum, item) => sum + Math.abs(item.quantity), 0), [transactions]);
  return <section className="border border-[#D1D1D6] bg-white">
    <div className="flex flex-wrap items-center gap-2 border-b border-[#E5E5EA] p-3"><div className="mr-auto"><h2 className="font-semibold">库存流水</h2><p className="mt-1 text-xs text-[#636366]">当前结果：入库 {formatQty(inbound)}，出库 {formatQty(outbound)}，共 {transactions.length} 条。</p></div><select value={materialId} onChange={(event) => setMaterialId(event.target.value)} className="h-9 min-w-64 border border-[#C7C7CC] px-2 text-sm"><option value="">全部物料</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select><button onClick={() => void load()} className="h-9 bg-[#007AFF] px-5 text-sm text-white">刷新</button></div>
    <div className="overflow-x-auto"><table className="w-full min-w-[1180px] table-fixed text-sm"><colgroup><col className="w-36"/><col className="w-28"/><col className="w-44"/><col className="w-32"/><col className="w-32"/><col className="w-24"/><col className="w-28"/><col className="w-40"/><col className="w-32"/><col className="w-40"/></colgroup><thead className="bg-[#F2F2F7] text-left text-xs text-[#636366]"><tr>{["时间","物料编码","物料名称","仓库","库位","数量","业务类型","来源单据","生产编号","备注"].map((item) => <th key={item} className="px-3 py-2.5 font-medium">{item}</th>)}</tr></thead><tbody>{loading ? <Empty text="正在加载流水..." /> : transactions.length === 0 ? <Empty text="暂无库存流水" /> : transactions.map((item) => <tr key={item.id} className="border-t border-[#E5E5EA]"><td className="px-3 py-2 text-xs text-[#636366]">{formatTime(item.created_at)}</td><td className="px-3 py-2 font-medium">{item.material_code}</td><td className="truncate px-3 py-2" title={item.material_name}>{item.material_name}</td><td className="px-3 py-2">{item.warehouse_name}</td><td className="px-3 py-2">{item.location_name}</td><td className={`px-3 py-2 text-right font-semibold ${item.quantity >= 0 ? "text-[#248A3D]" : "text-[#C62828]"}`}>{item.quantity >= 0 ? "+" : ""}{formatQty(item.quantity)} {item.unit}</td><td className="px-3 py-2">{item.transaction_type}</td><td className="truncate px-3 py-2" title={`${item.source_type} ${item.source_id}`}>{item.source_type} · {item.source_id}</td><td className="px-3 py-2">{item.production_no || "-"}</td><td className="truncate px-3 py-2 text-[#636366]" title={item.remark}>{item.remark || "-"}</td></tr>)}</tbody></table></div>
  </section>;
}

function Empty({ text }: { text: string }) { return <tr><td colSpan={10} className="h-36 text-center text-sm text-[#8E8E93]">{text}</td></tr>; }
function formatQty(value: number) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 3 }); }
function formatTime(value: string) { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : ""; }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
