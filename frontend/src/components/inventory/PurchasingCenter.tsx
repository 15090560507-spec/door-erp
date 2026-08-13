"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  cancelPurchaseOrder,
  confirmPurchaseOrder,
  createPurchaseOrder,
  createPurchaseReceipt,
  getPurchaseOrder,
  getPurchaseOrders,
  getPurchaseShortages,
} from "@/lib/inventoryApi";
import type { PurchaseOrder, PurchaseShortage } from "@/lib/inventoryTypes";

export default function PurchasingCenter({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [shortages, setShortages] = useState<PurchaseShortage[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [supplier, setSupplier] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [unitPrices, setUnitPrices] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");

  const load = useCallback(async (query = q) => {
    try {
      const [nextShortages, nextOrders] = await Promise.all([getPurchaseShortages(query), getPurchaseOrders({ q: query })]);
      setShortages(nextShortages); setOrders(nextOrders);
    } catch (error) { notify(message(error, "采购数据加载失败"), true); }
  }, [notify, q]);
  useEffect(() => {
    let cancelled = false;
    void Promise.all([getPurchaseShortages(), getPurchaseOrders()]).then(([nextShortages, nextOrders]) => {
      if (!cancelled) { setShortages(nextShortages); setOrders(nextOrders); }
    }).catch((error) => { if (!cancelled) notify(message(error, "采购数据加载失败"), true); });
    return () => { cancelled = true; };
  }, [notify]);

  const selectedRows = useMemo(() => shortages.filter((row) => selected.includes(row.requirement_item_id)), [shortages, selected]);
  const create = async () => {
    if (!supplier.trim() || selectedRows.length === 0) { notify("请选择采购缺口并填写供应商", true); return; }
    const grouped = new Map<number, PurchaseShortage[]>();
    selectedRows.forEach((row) => grouped.set(row.material_id, [...(grouped.get(row.material_id) || []), row]));
    setBusy(true);
    try {
      const result = await createPurchaseOrder({
        supplier, expected_date: expectedDate, remark: "由缺口池合并生成",
        items: Array.from(grouped.entries()).map(([materialId, rows]) => ({
          material_id: materialId,
          quantity: rows.reduce((sum, row) => sum + Number(row.demand_quantity), 0),
          unit: rows[0].unit,
          unit_price: Number(unitPrices[materialId] || 0),
          remark: "",
          allocations: rows.map((row) => ({ requirement_item_id: row.requirement_item_id, quantity: Number(row.demand_quantity) })),
        })),
      });
      notify(result.message); setSelected([]); await load(q);
    } catch (error) { notify(message(error, "采购单创建失败"), true); }
    finally { setBusy(false); }
  };

  const run = async (action: () => Promise<{ message: string }>) => {
    setBusy(true); try { const result = await action(); notify(result.message); await load(q); }
    catch (error) { notify(message(error, "采购操作失败"), true); }
    finally { setBusy(false); }
  };

  const receive = async (summary: PurchaseOrder) => {
    setBusy(true);
    try {
      const order = await getPurchaseOrder(summary.id);
      const items = (order.items || []).map((item) => ({ purchase_order_item_id: item.id, quantity: Math.max(0, item.ordered_quantity - item.cancelled_quantity - item.received_quantity - item.rejected_quantity) })).filter((item) => item.quantity > 0);
      if (!items.length) throw new Error("当前采购单没有可登记的到货数量");
      const result = await createPurchaseReceipt(order.id, { arrival_date: new Date().toISOString().slice(0, 10), remark: "", items });
      notify(result.message); await load(q);
    } catch (error) { notify(message(error, "到货登记失败"), true); }
    finally { setBusy(false); }
  };

  return <div className="space-y-4">
    <section className="border border-[#D1D1D6] bg-white">
      <header className="flex flex-wrap items-center gap-2 border-b border-[#E5E5EA] p-4"><div className="mr-auto"><h2 className="font-semibold">采购缺口池</h2><p className="mt-1 text-xs text-[#636366]">可跨门樘勾选，同一种物料自动合并为一条采购明细。</p></div><input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e)=>e.key==="Enter"&&void load(q)} placeholder="生产编号、物料" className="h-9 w-60 border border-[#C7C7CC] px-3 text-sm"/><button onClick={() => void load(q)} className="h-9 border border-[#C7C7CC] px-4 text-sm">查询</button></header>
      <div className="overflow-x-auto"><table className="w-full min-w-[1050px] table-fixed text-sm"><thead className="bg-[#F2F2F7] text-left text-xs text-[#636366]"><tr>{["选择","生产编号","要求交期","物料","规格","缺口","供应商建议","采购单价"].map((name)=><th key={name} className="px-3 py-2 font-medium">{name}</th>)}</tr></thead><tbody>{shortages.map((row)=><tr key={row.requirement_item_id} className="border-t border-[#E5E5EA]"><td className="px-3 py-3"><input type="checkbox" checked={selected.includes(row.requirement_item_id)} onChange={(e)=>setSelected(e.target.checked?[...selected,row.requirement_item_id]:selected.filter((id)=>id!==row.requirement_item_id))}/></td><td className="px-3 py-3 font-medium text-[#007AFF]">{row.production_no}</td><td className="px-3 py-3">{row.due_date||"-"}</td><td className="px-3 py-3"><div>{row.material_name}</div><div className="text-xs text-[#636366]">{row.material_code}</div></td><td className="px-3 py-3">{row.specification||"-"}</td><td className="px-3 py-3 font-semibold text-[#C62828]">{qty(row.demand_quantity)} {row.unit}</td><td className="px-3 py-3">{row.default_supplier||"-"}</td><td className="px-3 py-3"><input type="number" min="0" value={unitPrices[row.material_id]||""} onChange={(e)=>setUnitPrices({...unitPrices,[row.material_id]:Number(e.target.value)||0})} className="h-8 w-24 border border-[#C7C7CC] px-2"/></td></tr>)}{!shortages.length&&<tr><td colSpan={8} className="p-8 text-center text-[#8E8E93]">当前没有未覆盖缺口</td></tr>}</tbody></table></div>
      <div className="grid gap-2 border-t border-[#E5E5EA] p-4 md:grid-cols-[minmax(220px,1fr)_180px_auto]"><input value={supplier} onChange={(e)=>setSupplier(e.target.value)} placeholder="供应商（必填）" className="h-9 border border-[#C7C7CC] px-3 text-sm"/><input type="date" value={expectedDate} onChange={(e)=>setExpectedDate(e.target.value)} className="h-9 border border-[#C7C7CC] px-3 text-sm"/><button disabled={busy||!selectedRows.length} onClick={()=>void create()} className="h-9 bg-[#007AFF] px-5 text-sm text-white disabled:bg-[#C7C7CC]">合并生成采购单（{selectedRows.length} 项需求）</button></div>
    </section>
    <section className="border border-[#D1D1D6] bg-white"><header className="border-b border-[#E5E5EA] p-4"><h2 className="font-semibold">采购单与到货进度</h2></header><div className="divide-y divide-[#E5E5EA]">{orders.map((order)=><div key={order.id} className="p-4"><div className="flex flex-wrap items-center gap-3"><strong>{order.order_no}</strong><span className="text-sm">{order.supplier}</span><Status text={order.status}/><span className="text-xs text-[#636366]">预计 {order.expected_date||"-"} · {qty(order.received_quantity||0)}/{qty(order.ordered_quantity||0)} · ¥{Number(order.total_amount||0).toFixed(2)}</span><div className="flex-1"/>{order.status==="草稿"&&<button disabled={busy} onClick={()=>void run(()=>confirmPurchaseOrder(order.id))} className="h-8 bg-[#007AFF] px-3 text-xs text-white">确认下单</button>}{["已下单","部分到货"].includes(order.status)&&<button disabled={busy} onClick={()=>void receive(order)} className="h-8 bg-[#248A3D] px-3 text-xs text-white">登记全部剩余到货</button>}{["草稿","已下单","部分到货"].includes(order.status)&&<button disabled={busy} onClick={()=>void run(()=>cancelPurchaseOrder(order.id))} className="h-8 border border-[#C62828] px-3 text-xs text-[#C62828]">取消</button>}</div></div>)}{!orders.length&&<div className="p-8 text-center text-sm text-[#8E8E93]">暂无采购单</div>}</div></section>
  </div>;
}

function Status({text}:{text:string}){return <span className="bg-[#EDF3FF] px-2 py-1 text-xs text-[#315E9C]">{text}</span>}
function qty(value:number){return Number(value||0).toLocaleString("zh-CN",{maximumFractionDigits:4})}
function message(error:unknown,fallback:string){return (error as {userMessage?:string;message?:string})?.userMessage||(error as {message?:string})?.message||fallback}
