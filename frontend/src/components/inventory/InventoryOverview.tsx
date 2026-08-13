"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { confirmInventoryAdjustment, createInventoryAdjustment, getInventoryBalances, getInventoryMaterials, getInventoryWarehouses } from "@/lib/inventoryApi";
import type { InventoryBalance, InventoryMaterial, InventoryWarehouse } from "@/lib/inventoryTypes";

type Notice = (message: string, error?: boolean) => void;

export default function InventoryOverview({ notify }: { notify: Notice }) {
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [warehouses, setWarehouses] = useState<InventoryWarehouse[]>([]);
  const [q, setQ] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const [filters, setFilters] = useState({ q: "", warehouseId: "", lowOnly: false });
  const [loading, setLoading] = useState(true);
  const [adjusting, setAdjusting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextBalances, nextMaterials, nextWarehouses] = await Promise.all([
        getInventoryBalances({ q: filters.q || undefined, warehouse_id: filters.warehouseId ? Number(filters.warehouseId) : undefined, low_stock_only: filters.lowOnly || undefined }),
        getInventoryMaterials(), getInventoryWarehouses(),
      ]);
      setBalances(nextBalances); setMaterials(nextMaterials); setWarehouses(nextWarehouses);
    } catch (error) { notify(apiMessage(error, "库存数据加载失败"), true); }
    finally { setLoading(false); }
  }, [filters, notify]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  const totals = useMemo(() => ({
    materialCount: new Set(balances.map((item) => item.material_id)).size,
    onHand: balances.reduce((sum, item) => sum + item.on_hand, 0),
    available: balances.reduce((sum, item) => sum + item.available, 0),
    low: balances.filter((item) => item.available < item.minimum_stock).length,
  }), [balances]);

  return <div className="space-y-4">
    <section className="grid grid-cols-2 gap-px border border-[#D1D1D6] bg-[#D1D1D6] lg:grid-cols-4">
      <Metric label="有库存物料" value={totals.materialCount} /><Metric label="账面库存合计" value={formatQty(totals.onHand)} /><Metric label="可用库存合计" value={formatQty(totals.available)} /><Metric label="低于安全库存" value={totals.low} danger={totals.low > 0} />
    </section>
    <section className="border border-[#D1D1D6] bg-white">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#E5E5EA] p-3">
        <input value={q} onChange={(event) => setQ(event.target.value)} onKeyDown={(event) => event.key === "Enter" && setFilters({ q: q.trim(), warehouseId, lowOnly })} placeholder="搜索物料编码、名称、规格" className="h-9 min-w-64 flex-1 border border-[#C7C7CC] px-3 text-sm" />
        <select value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)} className="h-9 min-w-40 border border-[#C7C7CC] px-2 text-sm"><option value="">全部仓库</option>{warehouses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <label className="flex h-9 items-center gap-2 border border-[#C7C7CC] px-3 text-sm"><input type="checkbox" checked={lowOnly} onChange={(event) => setLowOnly(event.target.checked)} />只看低库存</label>
        <button onClick={() => setFilters({ q: q.trim(), warehouseId, lowOnly })} className="h-9 bg-[#007AFF] px-5 text-sm text-white">查询</button><button onClick={() => setAdjusting(true)} className="h-9 border border-[#007AFF] px-4 text-sm text-[#007AFF]">盘点调整</button>
      </div>
      <div className="overflow-x-auto"><table className="w-full min-w-[1120px] table-fixed text-sm">
        <colgroup><col className="w-28"/><col className="w-44"/><col className="w-36"/><col className="w-32"/><col className="w-36"/><col className="w-24"/><col className="w-24"/><col className="w-24"/><col className="w-24"/><col className="w-28"/></colgroup>
        <thead className="bg-[#F2F2F7] text-left text-xs text-[#636366]"><tr>{["物料编码","物料名称","规格","仓库","库位","在库","占用","可用","在途","状态"].map((item) => <th key={item} className="px-3 py-2.5 font-medium">{item}</th>)}</tr></thead>
        <tbody>{loading ? <RowEmpty text="正在加载库存..." /> : balances.length === 0 ? <RowEmpty text="暂无库存记录，可通过盘点调整建立期初库存" /> : balances.map((item) => { const low = item.available < item.minimum_stock; return <tr key={`${item.material_id}-${item.warehouse_id}-${item.location_id}`} className="border-t border-[#E5E5EA] hover:bg-[#F8F8FA]"><td className="px-3 py-2 font-medium">{item.material_code}</td><td className="truncate px-3 py-2" title={item.material_name}>{item.material_name}</td><td className="truncate px-3 py-2" title={item.specification}>{item.specification || "-"}</td><td className="px-3 py-2">{item.warehouse_name}</td><td className="px-3 py-2">{item.location_name}</td><td className="px-3 py-2 text-right">{formatQty(item.on_hand)} {item.unit}</td><td className="px-3 py-2 text-right">{formatQty(item.reserved)}</td><td className="px-3 py-2 text-right font-semibold">{formatQty(item.available)}</td><td className="px-3 py-2 text-right">{formatQty(item.purchase_in_transit + item.subcontract_in_transit)}</td><td className="px-3 py-2"><span className={`px-2 py-1 text-xs ${low ? "bg-[#FFECEC] text-[#C62828]" : "bg-[#EAF8ED] text-[#248A3D]"}`}>{low ? "需补充" : "正常"}</span></td></tr>; })}</tbody>
      </table></div>
    </section>
    {adjusting && <AdjustmentDialog materials={materials} warehouses={warehouses} onClose={() => setAdjusting(false)} onDone={async (message) => { setAdjusting(false); notify(message); await load(); }} notify={notify} />}
  </div>;
}

function AdjustmentDialog({ materials, warehouses, onClose, onDone, notify }: { materials: InventoryMaterial[]; warehouses: InventoryWarehouse[]; onClose: () => void; onDone: (message: string) => Promise<void>; notify: Notice }) {
  const firstWarehouse = warehouses[0];
  const [materialId, setMaterialId] = useState(""); const [warehouseId, setWarehouseId] = useState(firstWarehouse?.id ? String(firstWarehouse.id) : ""); const selectedWarehouse = warehouses.find((item) => item.id === Number(warehouseId)); const [locationId, setLocationId] = useState(firstWarehouse?.locations?.[0]?.id ? String(firstWarehouse.locations[0].id) : ""); const [quantity, setQuantity] = useState(0); const [remark, setRemark] = useState(""); const [busy, setBusy] = useState(false);
  const material = materials.find((item) => item.id === Number(materialId));
  const submit = async () => { if (!material || !warehouseId || !locationId || quantity === 0) { notify("请选择物料、仓库、库位，并填写非零调整数量", true); return; } setBusy(true); try { const draft = await createInventoryAdjustment({ remark, items: [{ material_id: material.id, warehouse_id: Number(warehouseId), location_id: Number(locationId), quantity, unit: material.unit, remark }] }); const result = await confirmInventoryAdjustment(draft.adjustment.id); await onDone(`${result.message}：${result.adjustment.document_no}`); } catch (error) { notify(apiMessage(error, "盘点调整失败"), true); } finally { setBusy(false); } };
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}><div className="w-full max-w-2xl border border-[#D1D1D6] bg-white p-5 shadow-2xl" onClick={(event) => event.stopPropagation()}><div className="flex items-center justify-between"><div><h3 className="font-semibold">库存盘点调整</h3><p className="mt-1 text-xs text-[#636366]">正数增加库存，负数减少库存；确认后形成不可篡改流水。</p></div><button onClick={onClose} aria-label="关闭" className="h-8 w-8 text-xl text-[#636366]">×</button></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><Field label="物料"><select value={materialId} onChange={(event) => setMaterialId(event.target.value)} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"><option value="">请选择物料</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name} {item.specification}</option>)}</select></Field><Field label="调整数量"><input type="number" step="0.001" value={quantity} onChange={(event) => setQuantity(Number(event.target.value) || 0)} className="h-10 w-full border border-[#C7C7CC] px-3 text-sm" /></Field><Field label="仓库"><select value={warehouseId} onChange={(event) => { const nextId = event.target.value; const nextWarehouse = warehouses.find((item) => item.id === Number(nextId)); setWarehouseId(nextId); setLocationId(nextWarehouse?.locations?.[0]?.id ? String(nextWarehouse.locations[0].id) : ""); }} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm">{warehouses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="库位"><select value={locationId} onChange={(event) => setLocationId(event.target.value)} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"><option value="">请选择库位</option>{selectedWarehouse?.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><label className="text-xs text-[#636366] sm:col-span-2">调整原因<textarea value={remark} onChange={(event) => setRemark(event.target.value)} className="mt-1 min-h-20 w-full border border-[#C7C7CC] p-3 text-sm text-[#1C1C1E]" placeholder="例如：期初库存、盘盈、盘亏、计量修正" /></label></div><div className="mt-5 flex justify-end gap-2"><button onClick={onClose} className="h-9 border border-[#C7C7CC] px-5 text-sm">取消</button><button disabled={busy} onClick={() => void submit()} className="h-9 bg-[#007AFF] px-5 text-sm text-white disabled:opacity-50">{busy ? "正在入账..." : "确认并入账"}</button></div></div></div>;
}

function Metric({ label, value, danger = false }: { label: string; value: number | string; danger?: boolean }) { return <div className="bg-white px-4 py-3"><div className="text-xs text-[#636366]">{label}</div><div className={`mt-1 text-xl font-semibold ${danger ? "text-[#C62828]" : "text-[#1C1C1E]"}`}>{value}</div></div>; }
function RowEmpty({ text }: { text: string }) { return <tr><td colSpan={10} className="h-36 text-center text-sm text-[#8E8E93]">{text}</td></tr>; }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="text-xs text-[#636366]">{label}<div className="mt-1">{children}</div></label>; }
function formatQty(value: number) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 3 }); }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
