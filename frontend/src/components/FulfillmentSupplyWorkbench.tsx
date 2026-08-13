"use client";

import { useCallback, useEffect, useState } from "react";
import { createFulfillmentInspection, getFulfillmentSupplyWorkbench, updateFulfillmentSupply } from "@/lib/fulfillmentApi";
import type { FulfillmentWorkbenchSupply } from "@/lib/fulfillmentTypes";

type Scope = "purchase" | "warehouse";

export default function FulfillmentSupplyWorkbench({ scope, notify }: { scope: Scope; notify: (message: string, error?: boolean) => void }) {
  const [rows, setRows] = useState<FulfillmentWorkbenchSupply[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows(await getFulfillmentSupplyWorkbench(scope, q)); }
    catch (error) { notify(apiMessage(error, `${scope === "purchase" ? "采购" : "仓库"}工作台加载失败`), true); }
    finally { setLoading(false); }
  }, [notify, q, scope]);
  useEffect(() => { void load(); }, [load]);

  const update = async (item: FulfillmentWorkbenchSupply, status: string) => {
    setBusyId(item.id);
    try {
      const result = await updateFulfillmentSupply(item.id, { status, handler_uid: item.handler_uid, supplier: item.supplier, actual_quantity: item.actual_quantity || item.required_quantity, unit_cost: item.unit_cost, remark: item.remark });
      notify(result.message); await load();
    } catch (error) { notify(apiMessage(error, "供应事项更新失败"), true); }
    finally { setBusyId(null); }
  };
  const inspect = async (item: FulfillmentWorkbenchSupply, result: "合格" | "不合格") => {
    setBusyId(item.id);
    try {
      const response = await createFulfillmentInspection(item.door_unit_id, { inspection_type: "来料检验", result, target_name: item.name, quantity: item.actual_quantity || item.required_quantity, defect_detail: result === "不合格" ? "来料检验不合格" : "", remark: "仓库来料确认" });
      notify(response.message); await load();
    } catch (error) { notify(apiMessage(error, "来料检验失败"), true); }
    finally { setBusyId(null); }
  };
  const configurePurchase = async (item: FulfillmentWorkbenchSupply) => {
    const handler = window.prompt("请输入采购经办人", item.handler_uid || "");
    if (handler === null) return;
    const supplier = window.prompt("请输入供应商或外协来源", item.supplier || "");
    if (supplier === null) return;
    await update({ ...item, handler_uid: handler.trim(), supplier: supplier.trim() }, item.status);
  };

  return <section className="border border-[#D1D1D6] bg-white">
    <header className="flex flex-wrap items-end gap-3 border-b border-[#E5E5EA] p-4">
      <div className="min-w-64 flex-1"><h2 className="font-semibold">{scope === "purchase" ? "采购工作台" : "仓库工作台"}</h2><p className="mt-1 text-xs text-[#636366]">{scope === "purchase" ? "集中办理外购、外协、定制件的经办、供应商和到货状态。" : "集中办理来料检验、入库和按清单发料，保留库存流水。"}</p></div>
      <input value={q} onChange={(event) => setQ(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void load()} placeholder="生产单号、客户、物料、供应商" className="h-10 w-72 border border-[#C7C7CC] px-3 text-sm" />
      <button onClick={() => void load()} className="h-10 border border-[#C7C7CC] px-4 text-sm">查询</button>
    </header>
    <div className="overflow-x-auto"><table className="w-full min-w-[1120px] text-sm"><thead className="bg-[#F7F7F9] text-left text-xs text-[#636366]"><tr>{["生产单/客户", "物料", "需求", "取得方式", "经办人", "供应商/来源", "状态", "操作"].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-3 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{rows.map((item) => <tr key={item.id} className="border-b border-[#F2F2F7] align-top">
      <td className="px-3 py-3"><strong className="block text-[#007AFF]">{item.production_no}</strong><span className="mt-1 block text-xs text-[#636366]">{item.customer}{item.project ? ` · ${item.project}` : ""}</span></td><td className="px-3 py-3"><strong>{item.name}</strong><span className="mt-1 block text-xs text-[#636366]">{item.category} · {item.specification || "无规格"}</span></td><td className="px-3 py-3">{item.actual_quantity || 0}/{item.required_quantity} {item.unit}</td><td className="px-3 py-3">{item.acquisition_method}</td><td className="px-3 py-3">{item.handler_uid || "未指定"}</td><td className="px-3 py-3">{item.supplier || "未填写"}</td><td className="px-3 py-3"><span className="bg-[#EDF3FF] px-2 py-1 text-xs text-[#315E9C]">{item.status}</span>{Boolean(item.inspection_passed) && <span className="ml-1 bg-[#EAF8ED] px-2 py-1 text-xs text-[#248A3D]">来料合格</span>}</td>
      <td className="px-3 py-3"><div className="flex flex-wrap gap-2">{scope === "purchase" && <Action disabled={busyId === item.id} onClick={() => void configurePurchase(item)}>设置经办</Action>}{scope === "purchase" && item.status === "待处理" && <Action disabled={busyId === item.id} onClick={() => void update(item, "办理中")}>开始办理</Action>}{scope === "purchase" && ["待处理", "办理中"].includes(item.status) && <Action disabled={busyId === item.id} onClick={() => void update(item, "到货待检")}>登记到货</Action>}{scope === "warehouse" && item.status === "到货待检" && !item.inspection_passed && <><Action disabled={busyId === item.id} onClick={() => void inspect(item, "合格")}>检验合格</Action><Action danger disabled={busyId === item.id} onClick={() => void inspect(item, "不合格")}>拒收</Action></>}{scope === "warehouse" && item.status === "到货待检" && Boolean(item.inspection_passed) && <Action disabled={busyId === item.id} onClick={() => void update(item, "已入库")}>确认入库</Action>}{scope === "warehouse" && item.status === "已入库" && <Action disabled={busyId === item.id} onClick={() => void update(item, "已发料")}>确认发料</Action>}{!availableAction(scope, item) && <span className="text-xs text-[#8E8E93]">无需操作</span>}</div></td>
    </tr>)}</tbody></table>{!loading && rows.length === 0 && <div className="flex min-h-52 items-center justify-center text-sm text-[#8E8E93]">当前没有相关事项</div>}{loading && <div className="flex min-h-52 items-center justify-center text-sm text-[#8E8E93]">正在加载...</div>}</div>
  </section>;
}

function availableAction(scope: Scope, item: FulfillmentWorkbenchSupply) { return scope === "purchase" || item.status === "到货待检" || item.status === "已入库"; }
function Action({ children, disabled, danger, onClick }: { children: React.ReactNode; disabled: boolean; danger?: boolean; onClick: () => void }) { return <button disabled={disabled} onClick={onClick} className={`h-8 border px-3 text-xs disabled:opacity-40 ${danger ? "border-[#C62828] text-[#C62828]" : "border-[#007AFF] text-[#007AFF]"}`}>{children}</button>; }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
