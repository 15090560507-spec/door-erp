"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { createInventoryMaterial, getInventoryMaterials, getInventoryWarehouses, updateInventoryMaterial } from "@/lib/inventoryApi";
import type { InventoryMaterial, InventoryWarehouse, MaterialPayload } from "@/lib/inventoryTypes";

const EMPTY: MaterialPayload = {
  code: "", name: "", category: "", specification: "", brand: "", unit: "件", material_type: "原材料",
  purchase_unit: "", purchase_conversion: 1, default_warehouse_id: null, default_location_id: null,
  default_supplier: "", minimum_stock: 0, safety_stock: 0, standard_sale_price: 0,
  reference_purchase_price: 0, can_sell: false, can_purchase: true, manage_stock: true,
  can_subcontract: false, remark: "", is_active: true,
};

export default function MaterialCatalog({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [warehouses, setWarehouses] = useState<InventoryWarehouse[]>([]);
  const [q, setQ] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<InventoryMaterial | "new" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextMaterials, nextWarehouses] = await Promise.all([
        getInventoryMaterials({ q: q || undefined, include_inactive: includeInactive }), getInventoryWarehouses(),
      ]);
      setMaterials(nextMaterials); setWarehouses(nextWarehouses);
    } catch (error) { notify(apiMessage(error, "物料与商品加载失败"), true); }
    finally { setLoading(false); }
  }, [includeInactive, notify, q]);

  useEffect(() => { void load(); }, [load]);
  const categories = useMemo(() => Array.from(new Set(materials.map((item) => item.category).filter(Boolean))).sort(), [materials]);

  return <section className="border border-[#D1D1D6] bg-white">
    <header className="flex flex-wrap items-center gap-2 border-b border-[#E5E5EA] p-4"><div className="mr-auto"><h2 className="font-semibold">物料与商品</h2><p className="mt-1 text-xs text-[#636366]">成品、原材料、配件、半成品、耗材和外协服务共用一套编码。</p></div><input value={q} onChange={(event) => setQ(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void load()} placeholder="编码、名称、规格" className="h-9 w-64 border border-[#C7C7CC] px-3 text-sm" /><label className="flex h-9 items-center gap-2 border border-[#C7C7CC] px-3 text-sm"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />含停用</label><button onClick={() => void load()} className="h-9 border border-[#C7C7CC] px-4 text-sm">查询</button><button onClick={() => setEditing("new")} className="h-9 bg-[#007AFF] px-4 text-sm text-white">新增物料或商品</button></header>
    <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">{loading ? <Empty text="正在加载..." /> : materials.length ? materials.map((item) => <button key={item.id} onClick={() => setEditing(item)} className={`border p-4 text-left transition-colors ${item.is_active ? "border-[#D1D1D6] hover:border-[#007AFF]" : "border-[#E5E5EA] bg-[#F7F7F9] text-[#8E8E93]"}`}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><strong className="block truncate text-sm">{item.name}</strong><span className="mt-1 block text-xs text-[#636366]">{item.code} · {item.specification || "无规格"}</span></div><span className="shrink-0 bg-[#F2F2F7] px-2 py-0.5 text-[11px]">{item.material_type}</span></div><div className="mt-4 flex flex-wrap gap-1.5"><Flag active={Boolean(item.can_sell)} text="销售" /><Flag active={Boolean(item.can_purchase)} text="采购" /><Flag active={Boolean(item.manage_stock)} text="库存" /><Flag active={Boolean(item.can_subcontract)} text="外协" /></div><div className="mt-4 grid grid-cols-3 gap-2 text-xs"><Info label="单位" value={item.unit} /><Info label="参考采购价" value={`¥${item.reference_purchase_price || 0}`} /><Info label="安全库存" value={String(item.safety_stock || item.minimum_stock || 0)} /></div></button>) : <Empty text="暂无物料与商品" />}</div>
    {editing && <MaterialDialog material={editing === "new" ? null : editing} warehouses={warehouses} categories={categories} onClose={() => setEditing(null)} onSaved={async (message) => { setEditing(null); notify(message); await load(); }} notify={notify} />}
  </section>;
}

function MaterialDialog({ material, warehouses, categories, onClose, onSaved, notify }: { material: InventoryMaterial | null; warehouses: InventoryWarehouse[]; categories: string[]; onClose: () => void; onSaved: (message: string) => Promise<void>; notify: (message: string, error?: boolean) => void }) {
  const [form, setForm] = useState<MaterialPayload>(material ? {
    code: material.code, name: material.name, category: material.category, specification: material.specification,
    brand: material.brand || "", unit: material.unit, material_type: material.material_type,
    purchase_unit: material.purchase_unit || "", purchase_conversion: material.purchase_conversion || 1,
    default_warehouse_id: material.default_warehouse_id, default_location_id: material.default_location_id,
    default_supplier: material.default_supplier, minimum_stock: material.minimum_stock,
    safety_stock: material.safety_stock || 0, standard_sale_price: material.standard_sale_price || 0,
    reference_purchase_price: material.reference_purchase_price || 0, can_sell: Boolean(material.can_sell),
    can_purchase: Boolean(material.can_purchase), manage_stock: Boolean(material.manage_stock),
    can_subcontract: Boolean(material.can_subcontract), remark: material.remark, is_active: Boolean(material.is_active),
  } : EMPTY);
  const [busy, setBusy] = useState(false);
  const warehouse = warehouses.find((item) => item.id === Number(form.default_warehouse_id));
  const set = <K extends keyof MaterialPayload>(key: K, value: MaterialPayload[K]) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async () => {
    if (!form.code.trim() || !form.name.trim() || !form.unit.trim() || !form.material_type.trim()) { notify("编码、名称、单位和类型为必填项", true); return; }
    setBusy(true);
    try { const result = material ? await updateInventoryMaterial(material.id, form) : await createInventoryMaterial(form); await onSaved(result.message); }
    catch (error) { notify(apiMessage(error, "保存失败"), true); }
    finally { setBusy(false); }
  };
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4" onMouseDown={onClose}><div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto border border-[#D1D1D6] bg-white p-5 shadow-2xl" onMouseDown={(event) => event.stopPropagation()}><div className="flex items-center justify-between"><div><h3 className="font-semibold">{material ? "编辑物料与商品" : "新增物料与商品"}</h3><p className="mt-1 text-xs text-[#636366]">编码保存后保持稳定，订单、采购和库存都使用这一条资料。</p></div><button onClick={onClose} aria-label="关闭" className="h-8 w-8 text-xl text-[#636366]">×</button></div><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Text label="编码 *" value={form.code} onChange={(value) => set("code", value)} disabled={Boolean(material)} /><Text label="名称 *" value={form.name} onChange={(value) => set("name", value)} /><label className="text-xs text-[#636366]">分类<input list="item-categories" value={form.category} onChange={(event) => set("category", event.target.value)} className="mt-1 h-10 w-full border border-[#C7C7CC] px-3 text-sm text-[#1C1C1E]" /><datalist id="item-categories">{categories.map((item) => <option key={item} value={item} />)}</datalist></label><Text label="品牌" value={form.brand || ""} onChange={(value) => set("brand", value)} /><Text label="规格型号" value={form.specification} onChange={(value) => set("specification", value)} /><Text label="基本单位 *" value={form.unit} onChange={(value) => set("unit", value)} /><Text label="采购单位" value={form.purchase_unit || ""} onChange={(value) => set("purchase_unit", value)} /><NumberField label="采购换算率" value={form.purchase_conversion || 1} onChange={(value) => set("purchase_conversion", value)} /><label className="text-xs text-[#636366]">类型 *<select value={form.material_type} onChange={(event) => set("material_type", event.target.value)} className="mt-1 h-10 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]">{["定制成品", "原材料", "配件", "半成品", "耗材", "外协服务", "采购件", "自制件", "外协件", "成品"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-xs text-[#636366]">默认仓库<select value={form.default_warehouse_id || ""} onChange={(event) => setForm({ ...form, default_warehouse_id: event.target.value ? Number(event.target.value) : null, default_location_id: null })} className="mt-1 h-10 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]"><option value="">未设置</option>{warehouses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="text-xs text-[#636366]">默认库位<select value={form.default_location_id || ""} onChange={(event) => set("default_location_id", event.target.value ? Number(event.target.value) : null)} className="mt-1 h-10 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]"><option value="">未设置</option>{warehouse?.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><NumberField label="安全库存" value={form.safety_stock || 0} onChange={(value) => { set("safety_stock", value); set("minimum_stock", value); }} /><NumberField label="标准销售价" value={form.standard_sale_price || 0} onChange={(value) => set("standard_sale_price", value)} /><NumberField label="参考采购价" value={form.reference_purchase_price || 0} onChange={(value) => set("reference_purchase_price", value)} /><div className="sm:col-span-2 lg:col-span-4"><span className="mb-2 block text-xs text-[#636366]">业务属性</span><div className="flex flex-wrap gap-4 border border-[#D1D1D6] p-3">{([['can_sell', '可销售'], ['can_purchase', '可采购'], ['manage_stock', '管理库存'], ['can_subcontract', '可外协']] as const).map(([key, label]) => <label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(form[key])} onChange={(event) => set(key, event.target.checked)} />{label}</label>)}</div></div><label className="text-xs text-[#636366] sm:col-span-2 lg:col-span-4">备注<textarea value={form.remark} onChange={(event) => set("remark", event.target.value)} className="mt-1 min-h-20 w-full border border-[#C7C7CC] p-3 text-sm text-[#1C1C1E]" /></label>{material && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(form.is_active)} onChange={(event) => set("is_active", event.target.checked)} />启用</label>}</div><div className="mt-5 flex justify-end gap-2"><button onClick={onClose} className="h-9 border border-[#C7C7CC] px-5 text-sm">取消</button><button disabled={busy} onClick={() => void submit()} className="h-9 bg-[#007AFF] px-5 text-sm text-white disabled:opacity-50">{busy ? "正在保存..." : "保存"}</button></div></div></div>;
}

function Flag({ active, text }: { active: boolean; text: string }) { return <span className={`px-2 py-0.5 text-[11px] ${active ? "bg-[#E7F7EA] text-[#248A3D]" : "bg-[#F2F2F7] text-[#8E8E93]"}`}>{text}</span>; }
function Info({ label, value }: { label: string; value: string }) { return <div><span className="block text-[#8E8E93]">{label}</span><strong className="mt-1 block truncate text-sm">{value}</strong></div>; }
function Text({ label, value, onChange, disabled = false }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean }) { return <label className="text-xs text-[#636366]">{label}<input disabled={disabled} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 h-10 w-full border border-[#C7C7CC] px-3 text-sm text-[#1C1C1E] disabled:bg-[#F2F2F7]" /></label>; }
function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) { return <label className="text-xs text-[#636366]">{label}<input type="number" min="0" step="0.01" value={value} onChange={(event) => onChange(Number(event.target.value) || 0)} className="mt-1 h-10 w-full border border-[#C7C7CC] px-3 text-sm text-[#1C1C1E]" /></label>; }
function Empty({ text }: { text: string }) { return <div className="col-span-full py-20 text-center text-sm text-[#8E8E93]">{text}</div>; }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
