"use client";

import { useCallback, useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/api";
import { getMaterialRequirement, getMaterialRequirements, reallocateMaterialRequirement } from "@/lib/inventoryApi";
import type { MaterialRequirement, MaterialRequirementSummary } from "@/lib/inventoryTypes";

export default function SupplyRequirements({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [rows, setRows] = useState<MaterialRequirementSummary[]>([]);
  const [selected, setSelected] = useState<MaterialRequirement | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await getMaterialRequirements({ q, status }));
    } catch (error) {
      notify(apiErrorMessage(error, "供应需求加载失败"), true);
    } finally {
      setLoading(false);
    }
  }, [notify, q, status]);

  useEffect(() => {
    let active = true;
    getMaterialRequirements({ q, status })
      .then((items) => { if (active) setRows(items); })
      .catch((error) => { if (active) notify(apiErrorMessage(error, "供应需求加载失败"), true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [notify, q, status]);

  const open = async (id: number) => {
    setBusy(true);
    try {
      setSelected(await getMaterialRequirement(id));
    } catch (error) {
      notify(apiErrorMessage(error, "供应需求加载失败"), true);
    } finally {
      setBusy(false);
    }
  };

  const reallocate = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const result = await reallocateMaterialRequirement(selected.id);
      setSelected(result.requirement);
      notify(result.message);
      await load();
    } catch (error) {
      notify(apiErrorMessage(error, "重新分配库存失败"), true);
    } finally {
      setBusy(false);
    }
  };

  return <section className="grid min-h-[620px] gap-4 xl:grid-cols-[460px_minmax(0,1fr)]">
    <aside className="border border-[#D1D1D6] bg-white">
      <div className="border-b border-[#E5E5EA] p-4">
        <div className="flex items-center justify-between">
          <div><h2 className="font-semibold">全厂供应需求</h2><p className="mt-1 text-xs text-[#636366]">技术包确认后自动汇总，普通库存仍归全厂共有。</p></div>
          <button onClick={() => void load()} className="h-8 border border-[#C7C7CC] px-3 text-xs">刷新</button>
        </div>
        <div className="mt-3 flex gap-2">
          <input value={q} onChange={(event) => setQ(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void load()} placeholder="需求单、生产编号、物料" className="h-9 min-w-0 flex-1 border border-[#C7C7CC] px-3 text-sm" />
          <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-9 w-28 border border-[#C7C7CC] px-2 text-sm"><option value="">全部状态</option><option>有缺口</option><option>已预留</option><option>已冻结</option></select>
        </div>
      </div>
      <div className="max-h-[720px] overflow-y-auto">
        {loading ? <div className="p-8 text-center text-sm text-[#8E8E93]">正在加载...</div> : rows.length === 0 ? <div className="p-8 text-center text-sm text-[#8E8E93]">暂无物料需求</div> : rows.map((row) => <button key={row.id} onClick={() => void open(row.id)} className={`block w-full border-b border-[#E5E5EA] p-4 text-left ${selected?.id === row.id ? "bg-[#EDF6FF]" : "bg-white hover:bg-[#F8F8FA]"}`}>
          <div className="flex items-center justify-between gap-3"><strong className="text-sm">{row.production_no}</strong><span className={`text-xs font-semibold ${row.shortage_quantity > 0 ? "text-[#C62828]" : "text-[#248A3D]"}`}>{row.status}</span></div>
          <div className="mt-1 text-xs text-[#636366]">{row.requirement_no} · V{row.version} · 交期 {row.due_date || "未设置"}</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs"><span>物料 {row.item_count} 项</span><span>已预留 {row.reserved_item_count} 项</span><span className={row.shortage_item_count > 0 ? "text-[#C62828]" : ""}>缺料 {row.shortage_item_count} 项</span></div>
        </button>)}
      </div>
    </aside>
    <div className="min-w-0 border border-[#D1D1D6] bg-white">
      {!selected ? <div className="flex min-h-[620px] items-center justify-center text-sm text-[#8E8E93]">选择左侧需求单查看物料明细</div> : <>
        <header className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] p-4"><div className="mr-auto"><h2 className="font-semibold">{selected.production_no} · {selected.requirement_no}</h2><p className="mt-1 text-xs text-[#636366]">技术版本 V{selected.version} · 交期 {selected.due_date || "未设置"}</p></div><button disabled={busy || selected.status === "已冻结"} onClick={() => void reallocate()} className="h-9 bg-[#007AFF] px-4 text-sm text-white disabled:bg-[#C7C7CC]">重新分配库存</button></header>
        <div className="grid gap-2 p-3 lg:hidden">{selected.items.map((item) => <article key={item.id} className="border border-[#E5E5EA] bg-[#FAFAFB] p-3"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><strong className="block truncate text-sm">{item.material_name}</strong><span className="mt-1 block truncate text-xs text-[#636366]">{item.material_code} · {item.specification || "无规格"}</span></div><span className={`shrink-0 px-2 py-1 text-xs font-semibold ${item.shortage_quantity > 0 ? "bg-[#FFECEC] text-[#C62828]" : "bg-[#EAF8ED] text-[#248A3D]"}`}>{item.status}</span></div><div className="mt-3 grid grid-cols-3 gap-2 text-xs"><RequirementInfo label="需求" value={`${item.required_quantity} ${item.unit}`}/><RequirementInfo label="已预留" value={String(item.reserved_quantity)} good/><RequirementInfo label="缺口" value={String(item.shortage_quantity)} danger={item.shortage_quantity > 0}/><RequirementInfo label="采购" value={String(item.purchased_quantity)}/><RequirementInfo label="到货" value={String(item.received_quantity)}/><RequirementInfo label="已领" value={String(item.issued_quantity)}/></div><div className="mt-3 border-t border-[#E5E5EA] pt-2 text-xs text-[#636366]">预留仓位：{item.reservations.filter((entry) => entry.status === "有效").map((entry) => `${entry.warehouse_name}/${entry.location_name} ${entry.quantity}`).join("；") || "未预留"}</div></article>)}</div>
        <div className="hidden overflow-x-auto p-4 lg:block"><table className="w-full min-w-[980px] table-fixed text-sm"><thead className="bg-[#F2F2F7] text-left text-xs text-[#636366]"><tr>{["物料", "规格", "需求", "已预留", "缺口", "采购", "到货", "已领", "状态", "预留仓位"].map((name) => <th key={name} className="px-3 py-2 font-medium">{name}</th>)}</tr></thead><tbody>{selected.items.map((item) => <tr key={item.id} className="border-b border-[#E5E5EA]"><td className="px-3 py-3"><div className="font-medium">{item.material_name}</div><div className="mt-1 text-xs text-[#636366]">{item.material_code}</div></td><td className="px-3 py-3">{item.specification || "-"}</td><td className="px-3 py-3">{item.required_quantity} {item.unit}</td><td className="px-3 py-3 text-[#248A3D]">{item.reserved_quantity}</td><td className={`px-3 py-3 font-semibold ${item.shortage_quantity > 0 ? "text-[#C62828]" : ""}`}>{item.shortage_quantity}</td><td className="px-3 py-3">{item.purchased_quantity}</td><td className="px-3 py-3">{item.received_quantity}</td><td className="px-3 py-3">{item.issued_quantity}</td><td className="px-3 py-3">{item.status}</td><td className="px-3 py-3 text-xs text-[#636366]">{item.reservations.filter((entry) => entry.status === "有效").map((entry) => `${entry.warehouse_name}/${entry.location_name} ${entry.quantity}`).join("；") || "-"}</td></tr>)}</tbody></table></div>
      </>}
    </div>
  </section>;
}

function RequirementInfo({ label, value, good = false, danger = false }: { label: string; value: string; good?: boolean; danger?: boolean }) {
  return <div><span className="block text-[#8E8E93]">{label}</span><strong className={`mt-0.5 block ${danger ? "text-[#C62828]" : good ? "text-[#248A3D]" : "text-[#3A3A3C]"}`}>{value}</strong></div>;
}
