"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, PackagePlus, Plus, Trash2 } from "lucide-react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import {
  cancelPurchaseOrder,
  confirmPurchaseOrder,
  createPurchaseOrder,
  createPurchaseReceipt,
  deletePurchaseOrder,
  getInventoryMaterials,
  getInventorySuppliers,
  getPurchaseOrder,
  getPurchaseOrders,
  getPurchaseShortages,
} from "@/lib/inventoryApi";
import type { InventoryMaterial, InventorySupplier, PurchaseOrder, PurchaseShortage } from "@/lib/inventoryTypes";

type ManualLine = { key: string; materialId: string; quantity: string; unitPrice: string; remark: string };

const blankLine = (): ManualLine => ({ key: crypto.randomUUID(), materialId: "", quantity: "", unitPrice: "", remark: "" });

export default function PurchasingCenter({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [shortages, setShortages] = useState<PurchaseShortage[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [suppliers, setSuppliers] = useState<InventorySupplier[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [supplier, setSupplier] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [unitPrices, setUnitPrices] = useState<Record<number, number>>({});
  const [manualOpen, setManualOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PurchaseOrder | null>(null);
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
    void Promise.all([getPurchaseShortages(), getPurchaseOrders(), getInventoryMaterials({ include_inactive: false }), getInventorySuppliers()]).then(([nextShortages, nextOrders, nextMaterials, nextSuppliers]) => {
      if (!cancelled) {
        setShortages(nextShortages);
        setOrders(nextOrders);
        setMaterials(nextMaterials.filter((item) => item.can_purchase !== 0));
        setSuppliers(nextSuppliers.filter((item) => item.is_active !== 0));
      }
    }).catch((error) => { if (!cancelled) notify(message(error, "采购数据加载失败"), true); });
    return () => { cancelled = true; };
  }, [notify]);

  const selectedRows = useMemo(() => shortages.filter((row) => selected.includes(row.requirement_item_id)), [shortages, selected]);
  const createFromShortage = async () => {
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

  const removeDraft = async () => {
    if (!pendingDelete) return;
    setBusy(true);
    try {
      const result = await deletePurchaseOrder(pendingDelete.id);
      setPendingDelete(null);
      notify(result.message);
      await load(q);
    } catch (error) { notify(message(error, "采购草稿删除失败"), true); }
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
      <header className="flex flex-wrap items-center gap-2 border-b border-[#E5E5EA] p-4"><div className="mr-auto"><h2 className="font-semibold">采购缺口池</h2><p className="mt-1 text-xs text-[#636366]">可跨门樘勾选，同一种物料自动合并为一条采购明细。</p></div><button type="button" onClick={() => setManualOpen(true)} className="ui-button ui-button--secondary"><PackagePlus size={15}/>手工备库</button><input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e)=>e.key==="Enter"&&void load(q)} placeholder="生产编号、物料" className="h-9 w-60 border border-[#C7C7CC] px-3 text-sm"/><button onClick={() => void load(q)} className="ui-button ui-button--primary">查询</button></header>
      <div className="overflow-x-auto"><table className="w-full min-w-[1050px] table-fixed text-sm"><thead className="bg-[#F2F2F7] text-left text-xs text-[#636366]"><tr>{["选择","生产编号","要求交期","物料","规格","缺口","供应商建议","采购单价"].map((name)=><th key={name} className="px-3 py-2 font-medium">{name}</th>)}</tr></thead><tbody>{shortages.map((row)=><tr key={row.requirement_item_id} className="border-t border-[#E5E5EA]"><td className="px-3 py-3"><input type="checkbox" checked={selected.includes(row.requirement_item_id)} onChange={(e)=>setSelected(e.target.checked?[...selected,row.requirement_item_id]:selected.filter((id)=>id!==row.requirement_item_id))}/></td><td className="px-3 py-3 font-medium text-[#007AFF]">{row.production_no}</td><td className="px-3 py-3">{row.due_date||"-"}</td><td className="px-3 py-3"><div>{row.material_name}</div><div className="text-xs text-[#636366]">{row.material_code}</div></td><td className="px-3 py-3">{row.specification||"-"}</td><td className="px-3 py-3 font-semibold text-[#C62828]">{qty(row.demand_quantity)} {row.unit}</td><td className="px-3 py-3">{row.default_supplier||"-"}</td><td className="px-3 py-3"><input type="number" min="0" value={unitPrices[row.material_id]||""} onChange={(e)=>setUnitPrices({...unitPrices,[row.material_id]:Number(e.target.value)||0})} className="h-8 w-24 border border-[#C7C7CC] px-2"/></td></tr>)}{!shortages.length&&<tr><td colSpan={8} className="p-8 text-center text-[#8E8E93]">当前没有未覆盖缺口</td></tr>}</tbody></table></div>
      <div className="grid gap-2 border-t border-[#E5E5EA] p-4 md:grid-cols-[minmax(220px,1fr)_180px_auto]"><input value={supplier} onChange={(e)=>setSupplier(e.target.value)} list="purchase-suppliers" placeholder="供应商（必填）" className="h-9 border border-[#C7C7CC] px-3 text-sm"/><input type="date" value={expectedDate} onChange={(e)=>setExpectedDate(e.target.value)} className="h-9 border border-[#C7C7CC] px-3 text-sm"/><button disabled={busy||!selectedRows.length} onClick={()=>void createFromShortage()} className="ui-button ui-button--primary">合并生成采购单（{selectedRows.length} 项需求）</button></div>
    </section>
    <section className="border border-[#D1D1D6] bg-white"><header className="border-b border-[#E5E5EA] p-4"><h2 className="font-semibold">采购单与到货进度</h2></header><div className="divide-y divide-[#E5E5EA]">{orders.map((order)=><div key={order.id} className="p-4"><div className="flex flex-wrap items-center gap-3"><strong>{order.order_no}</strong><span className="text-sm">{order.supplier}</span><Status text={order.status}/><span className="text-xs text-[#636366]">预计 {order.expected_date||"-"} · {qty(order.received_quantity||0)}/{qty(order.ordered_quantity||0)} · ¥{Number(order.total_amount||0).toFixed(2)}</span><div className="flex-1"/>{order.status==="草稿"&&<><button disabled={busy} onClick={()=>void run(()=>confirmPurchaseOrder(order.id))} className="ui-button ui-button--primary">确认下单</button><button disabled={busy} onClick={()=>setPendingDelete(order)} className="ui-button ui-button--danger"><Trash2 size={14}/>删除草稿</button></>}{["已下单","部分到货"].includes(order.status)&&<><button disabled={busy} onClick={()=>void receive(order)} className="ui-button ui-button--primary">登记全部剩余到货</button><button disabled={busy} onClick={()=>void run(()=>cancelPurchaseOrder(order.id))} className="ui-button ui-button--danger">取消剩余</button></>}</div></div>)}{!orders.length&&<div className="p-8 text-center text-sm text-[#8E8E93]">暂无采购单</div>}</div></section>
    <datalist id="purchase-suppliers">{suppliers.map((item)=><option key={item.id} value={item.name}/>)}</datalist>
    <ManualPurchaseDialog open={manualOpen} materials={materials} suppliers={suppliers} busy={busy} onClose={()=>setManualOpen(false)} onSubmit={async(payload)=>{setBusy(true);try{const result=await createPurchaseOrder(payload);setManualOpen(false);notify(result.message);await load(q);}catch(error){notify(message(error,"手工采购单创建失败"),true);}finally{setBusy(false);}}}/>
    <ViewportDialog open={Boolean(pendingDelete)} title="删除采购草稿" description="草稿删除后不可恢复，未确认的需求分配不会受影响。" size="small" onClose={()=>setPendingDelete(null)} footer={<><button type="button" className="ui-button ui-button--secondary" onClick={()=>setPendingDelete(null)}>取消</button><button type="button" className="ui-button ui-button--danger" disabled={busy} onClick={()=>void removeDraft()}><Trash2 size={15}/>确认删除</button></>}><p className="text-sm text-[#48484A]">确定删除采购单 <strong>{pendingDelete?.order_no}</strong> 吗？</p></ViewportDialog>
  </div>;
}

function ManualPurchaseDialog({ open, materials, suppliers, busy, onClose, onSubmit }: { open: boolean; materials: InventoryMaterial[]; suppliers: InventorySupplier[]; busy: boolean; onClose: () => void; onSubmit: (payload: Parameters<typeof createPurchaseOrder>[0]) => Promise<void> }) {
  const [supplier, setSupplier] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [remark, setRemark] = useState("");
  const [lines, setLines] = useState<ManualLine[]>([]);

  useEffect(() => {
    if (open) {
      setSupplier("");
      setExpectedDate("");
      setRemark("");
      setLines([blankLine()]);
    }
  }, [open]);

  const update = (key: string, changes: Partial<ManualLine>) => setLines((current) => current.map((line) => line.key === key ? { ...line, ...changes } : line));
  const total = lines.reduce((sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.unitPrice) || 0), 0);
  const submit = async () => {
    const selected = lines.map((line) => ({ line, material: materials.find((item) => item.id === Number(line.materialId)) }));
    if (!supplier.trim() || !selected.length || selected.some(({ line, material }) => !material || Number(line.quantity) <= 0)) return;
    await onSubmit({
      supplier: supplier.trim(),
      expected_date: expectedDate,
      remark,
      items: selected.map(({ line, material }) => ({
        material_id: material!.id,
        quantity: Number(line.quantity),
        unit: material!.unit,
        unit_price: Number(line.unitPrice) || 0,
        remark: line.remark,
        allocations: [],
      })),
    });
  };

  return <ViewportDialog open={open} title="手工备库采购" description="用于公共库存补充，不需要关联具体 TM 订单；确认采购后进入在途。" size="wide" onClose={onClose} footer={<><span className="mr-auto text-sm text-[#636366]">预计金额 <strong className="ml-1 text-[#1C1C1E]">¥{total.toFixed(2)}</strong></span><button type="button" className="ui-button ui-button--secondary" onClick={onClose}>取消</button><button type="button" className="ui-button ui-button--primary" disabled={busy || !supplier.trim() || lines.some((line) => !line.materialId || Number(line.quantity) <= 0)} onClick={() => void submit()}><PackagePlus size={15}/>保存采购草稿</button></>}>
    <div className="grid gap-3 md:grid-cols-3"><Field label="供应商 *"><input value={supplier} onChange={(event)=>setSupplier(event.target.value)} list="manual-purchase-suppliers" placeholder="选择或输入供应商" className="h-10 w-full border border-[#C7C7CC] px-3 text-sm"/></Field><Field label="预计到货"><input type="date" value={expectedDate} onChange={(event)=>setExpectedDate(event.target.value)} className="h-10 w-full border border-[#C7C7CC] px-3 text-sm"/></Field><Field label="采购说明"><input value={remark} onChange={(event)=>setRemark(event.target.value)} placeholder="例如：常备板材补库" className="h-10 w-full border border-[#C7C7CC] px-3 text-sm"/></Field></div>
    <div className="mt-5 space-y-2">
      <div className="flex items-center justify-between"><strong className="text-sm">采购明细</strong><button type="button" className="ui-button ui-button--secondary" onClick={()=>setLines((current)=>[...current,blankLine()])}><Plus size={15}/>添加物料</button></div>
      {lines.map((line,index)=>{const material=materials.find((item)=>item.id===Number(line.materialId));return <div key={line.key} className="grid gap-2 border border-[#E5E5EA] bg-[#FAFAFB] p-3 lg:grid-cols-[32px_minmax(220px,2fr)_110px_90px_120px_minmax(140px,1fr)_72px]"><span className="flex h-10 items-center text-xs text-[#8E8E93]">{index+1}</span><Field label="物料 *"><select value={line.materialId} onChange={(event)=>{const next=materials.find((item)=>item.id===Number(event.target.value));update(line.key,{materialId:event.target.value,unitPrice:next?.reference_purchase_price?String(next.reference_purchase_price):line.unitPrice});}} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"><option value="">请选择</option>{materials.map((item)=><option key={item.id} value={item.id}>{item.code} · {item.name} {item.specification}</option>)}</select></Field><Field label="数量 *"><input type="number" min="0" step="0.001" value={line.quantity} onChange={(event)=>update(line.key,{quantity:event.target.value})} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"/></Field><Field label="单位"><div className="flex h-10 items-center border border-[#E5E5EA] bg-white px-3 text-sm">{material?.unit||"-"}</div></Field><Field label="采购单价"><input type="number" min="0" step="0.01" value={line.unitPrice} onChange={(event)=>update(line.key,{unitPrice:event.target.value})} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"/></Field><Field label="行备注"><input value={line.remark} onChange={(event)=>update(line.key,{remark:event.target.value})} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"/></Field><div className="flex items-end gap-1"><button type="button" title="复制本行" aria-label="复制本行" onClick={()=>setLines((current)=>[...current.slice(0,index+1),{...line,key:crypto.randomUUID()},...current.slice(index+1)])} className="ui-button ui-button--quiet h-10 w-8 px-0"><Copy size={15}/></button><button type="button" title="删除本行" aria-label="删除本行" disabled={lines.length===1} onClick={()=>setLines((current)=>current.filter((item)=>item.key!==line.key))} className="ui-button ui-button--danger h-10 w-8 px-0"><Trash2 size={15}/></button></div></div>;})}
    </div>
    <datalist id="manual-purchase-suppliers">{suppliers.map((item)=><option key={item.id} value={item.name}/>)}</datalist>
  </ViewportDialog>;
}

function Status({text}:{text:string}){return <span className="bg-[#EDF3FF] px-2 py-1 text-xs text-[#315E9C]">{text}</span>}
function Field({label,children}:{label:string;children:React.ReactNode}){return <label className="text-xs text-[#636366]">{label}<div className="mt-1">{children}</div></label>}
function qty(value:number){return Number(value||0).toLocaleString("zh-CN",{maximumFractionDigits:4})}
function message(error:unknown,fallback:string){return (error as {userMessage?:string;message?:string})?.userMessage||(error as {message?:string})?.message||fallback}
