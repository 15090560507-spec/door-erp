"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
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
      <div className="grid gap-2 p-3 lg:hidden">
        {loading ? <CompactEmpty text="正在加载库存..." /> : balances.length === 0 ? <CompactEmpty text="暂无库存记录，可通过盘点调整建立期初库存" /> : balances.map((item) => {
          const low = item.available < item.minimum_stock;
          return <article key={`${item.material_id}-${item.warehouse_id}-${item.location_id}`} className="border border-[#E5E5EA] bg-[#FAFAFB] p-3">
            <div className="flex items-start justify-between gap-3"><div className="min-w-0"><strong className="block truncate text-sm">{item.material_name}</strong><span className="mt-1 block truncate text-xs text-[#636366]">{item.material_code} · {item.specification || "无规格"}</span></div><span className={`shrink-0 px-2 py-1 text-xs ${low ? "bg-[#FFECEC] text-[#C62828]" : "bg-[#EAF8ED] text-[#248A3D]"}`}>{low ? "需补充" : "正常"}</span></div>
            <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3"><CompactInfo label="仓库 / 库位" value={`${item.warehouse_name} / ${item.location_name}`} /><CompactInfo label="在库" value={`${formatQty(item.on_hand)} ${item.unit}`} /><CompactInfo label="占用" value={formatQty(item.reserved)} /><CompactInfo label="可用" value={formatQty(item.available)} strong /><CompactInfo label="在途" value={formatQty(item.purchase_in_transit + item.subcontract_in_transit)} /></div>
          </article>;
        })}
      </div>
      <div className="hidden overflow-x-auto lg:block"><table className="w-full min-w-[1120px] table-fixed text-sm">
        <colgroup><col className="w-28"/><col className="w-44"/><col className="w-36"/><col className="w-32"/><col className="w-36"/><col className="w-24"/><col className="w-24"/><col className="w-24"/><col className="w-24"/><col className="w-28"/></colgroup>
        <thead className="bg-[#F2F2F7] text-left text-xs text-[#636366]"><tr>{["物料编码","物料名称","规格","仓库","库位","在库","占用","可用","在途","状态"].map((item) => <th key={item} className="px-3 py-2.5 font-medium">{item}</th>)}</tr></thead>
        <tbody>{loading ? <RowEmpty text="正在加载库存..." /> : balances.length === 0 ? <RowEmpty text="暂无库存记录，可通过盘点调整建立期初库存" /> : balances.map((item) => { const low = item.available < item.minimum_stock; return <tr key={`${item.material_id}-${item.warehouse_id}-${item.location_id}`} className="border-t border-[#E5E5EA] hover:bg-[#F8F8FA]"><td className="px-3 py-2 font-medium">{item.material_code}</td><td className="truncate px-3 py-2" title={item.material_name}>{item.material_name}</td><td className="truncate px-3 py-2" title={item.specification}>{item.specification || "-"}</td><td className="px-3 py-2">{item.warehouse_name}</td><td className="px-3 py-2">{item.location_name}</td><td className="px-3 py-2 text-right">{formatQty(item.on_hand)} {item.unit}</td><td className="px-3 py-2 text-right">{formatQty(item.reserved)}</td><td className="px-3 py-2 text-right font-semibold">{formatQty(item.available)}</td><td className="px-3 py-2 text-right">{formatQty(item.purchase_in_transit + item.subcontract_in_transit)}</td><td className="px-3 py-2"><span className={`px-2 py-1 text-xs ${low ? "bg-[#FFECEC] text-[#C62828]" : "bg-[#EAF8ED] text-[#248A3D]"}`}>{low ? "需补充" : "正常"}</span></td></tr>; })}</tbody>
      </table></div>
    </section>
    {adjusting && <AdjustmentDialog materials={materials} warehouses={warehouses} onClose={() => setAdjusting(false)} onDone={async (message) => { setAdjusting(false); notify(message); await load(); }} notify={notify} />}
  </div>;
}

function AdjustmentDialog({ materials, warehouses, onClose, onDone, notify }: { materials: InventoryMaterial[]; warehouses: InventoryWarehouse[]; onClose: () => void; onDone: (message: string) => Promise<void>; notify: Notice }) {
  type Line = { key: string; materialId: string; warehouseId: string; locationId: string; quantity: string; remark: string };
  const newLine = (): Line => { const warehouse = warehouses[0]; return { key: crypto.randomUUID(), materialId: "", warehouseId: warehouse?.id ? String(warehouse.id) : "", locationId: warehouse?.locations?.[0]?.id ? String(warehouse.locations[0].id) : "", quantity: "", remark: "" }; };
  const [lines, setLines] = useState<Line[]>(() => [newLine()]);
  const [remark, setRemark] = useState("");
  const [busy, setBusy] = useState(false);
  const update = (key: string, changes: Partial<Line>) => setLines((current) => current.map((line) => line.key === key ? { ...line, ...changes } : line));
  const valid = lines.length > 0 && lines.every((line) => line.materialId && line.warehouseId && line.locationId && Number(line.quantity) !== 0);
  const submit = async () => {
    if (!valid) { notify("请完整选择物料、仓库、库位，并填写非零调整数量", true); return; }
    setBusy(true);
    try {
      const draft = await createInventoryAdjustment({
        remark,
        items: lines.map((line) => {
          const material = materials.find((item) => item.id === Number(line.materialId))!;
          return { material_id: material.id, warehouse_id: Number(line.warehouseId), location_id: Number(line.locationId), quantity: Number(line.quantity), unit: material.unit, remark: line.remark };
        }),
      });
      const result = await confirmInventoryAdjustment(draft.adjustment.id);
      await onDone(`${result.message}：${result.adjustment.document_no}`);
    } catch (error) { notify(apiMessage(error, "盘点调整失败"), true); }
    finally { setBusy(false); }
  };
  return <ViewportDialog open title="库存盘点调整" description="可一次录入多种物料；正数增加、负数减少，确认后形成不可篡改流水。" size="wide" onClose={onClose} footer={<><button type="button" onClick={onClose} className="ui-button ui-button--secondary">取消</button><button type="button" disabled={busy || !valid} onClick={() => void submit()} className="ui-button ui-button--primary">{busy ? "正在入账..." : `确认 ${lines.length} 项并入账`}</button></>}>
    <Field label="整单调整原因"><textarea value={remark} onChange={(event) => setRemark(event.target.value)} className="min-h-20 w-full border border-[#C7C7CC] p-3 text-sm text-[#1C1C1E]" placeholder="例如：期初库存、月末盘点、账实差异修正" /></Field>
    <div className="mt-5 space-y-2"><div className="flex items-center justify-between"><strong className="text-sm">调整明细</strong><button type="button" className="ui-button ui-button--secondary" onClick={() => setLines((current) => [...current, newLine()])}><Plus size={15}/>添加物料</button></div>
      {lines.map((line, index) => { const warehouse = warehouses.find((item) => item.id === Number(line.warehouseId)); const material = materials.find((item) => item.id === Number(line.materialId)); return <div key={line.key} className="grid gap-2 border border-[#E5E5EA] bg-[#FAFAFB] p-3 lg:grid-cols-[32px_minmax(220px,2fr)_135px_145px_120px_minmax(140px,1fr)_40px]"><span className="flex h-10 items-center text-xs text-[#8E8E93]">{index + 1}</span><Field label="物料 *"><select value={line.materialId} onChange={(event) => update(line.key, { materialId: event.target.value })} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"><option value="">请选择</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name} {item.specification}</option>)}</select></Field><Field label="仓库 *"><select value={line.warehouseId} onChange={(event) => { const next = warehouses.find((item) => item.id === Number(event.target.value)); update(line.key, { warehouseId: event.target.value, locationId: next?.locations?.[0]?.id ? String(next.locations[0].id) : "" }); }} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm">{warehouses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="库位 *"><select value={line.locationId} onChange={(event) => update(line.key, { locationId: event.target.value })} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm"><option value="">请选择</option>{warehouse?.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label={`调整数量${material ? ` (${material.unit})` : ""} *`}><input type="number" step="0.001" value={line.quantity} onChange={(event) => update(line.key, { quantity: event.target.value })} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm" placeholder="正增负减" /></Field><Field label="行备注"><input value={line.remark} onChange={(event) => update(line.key, { remark: event.target.value })} className="h-10 w-full border border-[#C7C7CC] px-2 text-sm" /></Field><div className="flex items-end"><button type="button" title="删除本行" aria-label="删除本行" disabled={lines.length === 1} onClick={() => setLines((current) => current.filter((item) => item.key !== line.key))} className="ui-button ui-button--danger h-10 w-10 px-0"><Trash2 size={15}/></button></div></div>; })}
    </div>
  </ViewportDialog>;
}

function Metric({ label, value, danger = false }: { label: string; value: number | string; danger?: boolean }) { return <div className="bg-white px-4 py-3"><div className="text-xs text-[#636366]">{label}</div><div className={`mt-1 text-xl font-semibold ${danger ? "text-[#C62828]" : "text-[#1C1C1E]"}`}>{value}</div></div>; }
function CompactEmpty({ text }: { text: string }) { return <div className="py-16 text-center text-sm text-[#8E8E93]">{text}</div>; }
function CompactInfo({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) { return <div className="min-w-0"><span className="block text-[#8E8E93]">{label}</span><span className={`mt-0.5 block truncate ${strong ? "font-semibold text-[#1C1C1E]" : "text-[#3A3A3C]"}`}>{value}</span></div>; }
function RowEmpty({ text }: { text: string }) { return <tr><td colSpan={10} className="h-36 text-center text-sm text-[#8E8E93]">{text}</td></tr>; }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="text-xs text-[#636366]">{label}<div className="mt-1">{children}</div></label>; }
function formatQty(value: number) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 3 }); }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
