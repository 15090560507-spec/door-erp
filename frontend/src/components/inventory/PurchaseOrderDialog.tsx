"use client";

import { Copy, PackagePlus, Plus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import PurchaseCatalogInput from "./PurchaseCatalogInput";
import { createPurchaseOrder, getInventoryMaterials, getInventorySuppliers, getInventorySupplierItems } from "@/lib/inventoryApi";
import type { InventoryMaterial, InventorySupplier, InventorySupplierItem } from "@/lib/inventoryTypes";

type Line = { key: string; materialId?: number; name: string; specification: string; unit: string; quantity: string; price: string; priceEdited: boolean; remark: string };
const blankLine = (): Line => ({ key: crypto.randomUUID(), name: "", specification: "", unit: "", quantity: "", price: "", priceEdited: false, remark: "" });
const inputClass = "h-10 w-full min-w-0 border border-[#C7C7CC] bg-white px-3 text-sm disabled:bg-[#F2F2F7]";

export default function PurchaseOrderDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (message: string) => void }) {
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [suppliers, setSuppliers] = useState<InventorySupplier[]>([]);
  const [supplies, setSupplies] = useState<InventorySupplierItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [supplier, setSupplier] = useState("");
  const [supplierId, setSupplierId] = useState<number>();
  const [expectedDate, setExpectedDate] = useState("");
  const [remark, setRemark] = useState("");
  const [lines, setLines] = useState<Line[]>(() => [blankLine()]);
  const request = useRef<{ body: string; key: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getInventoryMaterials({ include_inactive: false }), getInventorySuppliers(), getInventorySupplierItems()])
      .then(([nextMaterials, nextSuppliers, nextSupplies]) => {
        if (cancelled) return;
        setMaterials(nextMaterials.filter(item => item.can_purchase !== 0));
        setSuppliers(nextSuppliers.filter(item => item.is_active !== 0)); setSupplies(nextSupplies); setLoadError("");
      }).catch(error => { if (!cancelled) setLoadError(message(error)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reload]);

  const resolvedSupplier = supplierId ?? (suppliers.filter(item => item.name === supplier.trim()).length === 1 ? suppliers.find(item => item.name === supplier.trim())?.id : undefined);
  const suggestedPrice = (materialId: number | undefined, nextSupplier: number | undefined) => {
    const relation = supplies.find(item => item.material_id === materialId && item.supplier_id === nextSupplier);
    if (relation && relation.conversion_rate > 0) return String(Number((relation.tax_inclusive_price / relation.conversion_rate).toFixed(6)));
    const material = materials.find(item => item.id === materialId);
    return material?.reference_purchase_price ? String(material.reference_purchase_price) : "";
  };
  const changeSupplier = (name: string, id?: number) => {
    setSupplier(name); setSupplierId(id);
    const exact = suppliers.filter(item => item.name === name.trim());
    const nextId = id ?? (exact.length === 1 ? exact[0].id : undefined);
    setLines(current => current.map(line => line.priceEdited ? line : { ...line, price: suggestedPrice(line.materialId, nextId) }));
  };
  const update = (key: string, changes: Partial<Line>) => setLines(current => current.map(line => line.key === key ? { ...line, ...changes } : line));
  const valid = !loading && !loadError && supplier.trim() && lines.length > 0 && lines.every(line =>
    line.name.trim() && line.unit.trim() && Number.isFinite(Number(line.quantity)) && Number(line.quantity) > 0 && Number.isFinite(Number(line.price)) && Number(line.price) >= 0);
  const total = lines.reduce((sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.price) || 0), 0);
  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true); setError("");
    const payload = { supplier: supplier.trim(), supplier_id: resolvedSupplier, expected_date: expectedDate, remark,
      items: lines.map(line => ({ material_id: line.materialId, material_name: line.name.trim(), specification: line.specification.trim(),
        unit: line.unit.trim(), quantity: Number(line.quantity), unit_price: Number(line.price), remark: line.remark, allocations: [] })) };
    const body = JSON.stringify(payload);
    if (request.current?.body !== body) request.current = { body, key: crypto.randomUUID() };
    try { const result = await createPurchaseOrder({ ...payload, request_key: request.current!.key }); onCreated(result.message); }
    catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  };

  return <ViewportDialog open title="新建采购单" size="wide" onClose={() => { if (!busy) onClose(); }} closeOnBackdrop={false}
    footer={<><span className="mr-auto text-sm">预计金额 <strong>¥{Number.isFinite(total) ? total.toFixed(2) : "-"}</strong></span>
      <button type="button" className="ui-button ui-button--secondary" disabled={busy} onClick={onClose}>取消</button>
      <button type="button" className="ui-button ui-button--primary" disabled={!valid || busy} onClick={() => void submit()}><PackagePlus size={15} />{busy ? "保存中…" : "保存采购草稿"}</button></>}>
    {loading && <p role="status" className="mb-3 text-sm">正在加载商品与供货资料…</p>}
    {loadError && <div role="alert" className="mb-3 text-sm text-red-700">{loadError}<button type="button" className="ui-button ui-button--secondary ml-2" onClick={() => { setLoading(true); setReload(value => value + 1); }}>重试</button></div>}
    {error && <p role="alert" className="mb-3 text-sm text-red-700">{error}</p>}
    <fieldset disabled={busy || loading || Boolean(loadError)} className="min-w-0 space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="供应商 *"><PurchaseCatalogInput label="供应商" value={supplier} onChange={value => changeSupplier(value)}
          onSelect={id => { const selected = suppliers.find(item => item.id === id)!; changeSupplier(selected.name, id); }}
          choices={suppliers.map(item => ({ id: item.id, name: item.name, detail: [item.code, item.contact_name, item.phone].filter(Boolean).join(" · "), search: [item.name, item.code, item.short_name, item.phone].join(" ") }))} /></Field>
        <Field label="预计到货"><input aria-label="预计到货" type="date" value={expectedDate} onChange={event => setExpectedDate(event.target.value)} className={inputClass} /></Field>
        <Field label="采购说明"><input aria-label="采购说明" value={remark} onChange={event => setRemark(event.target.value)} className={inputClass} /></Field>
      </div>
      <div className="flex items-center justify-between"><h3 className="font-semibold">采购明细</h3><button type="button" className="ui-button ui-button--secondary" onClick={() => setLines(current => [...current, blankLine()])}><Plus size={15} />添加物料</button></div>
      <div className="space-y-3">{lines.map((line, index) => <article key={line.key} className="border border-[#E5E5EA] p-3" aria-label={`采购明细 ${index + 1}`}>
        <div className="mb-3 flex items-center gap-2"><strong className="mr-auto text-sm">{index + 1}. {line.materialId ? "已有商品" : "新商品"}</strong>
          {line.materialId && <button type="button" className="ui-button ui-button--secondary" onClick={() => update(line.key, { materialId: undefined })}><Plus size={15} />另建规格</button>}
          <button type="button" title="复制本行" aria-label="复制本行" className="ui-button ui-button--quiet" onClick={() => setLines(current => [...current.slice(0, index + 1), { ...line, key: crypto.randomUUID() }, ...current.slice(index + 1)])}><Copy size={15} /></button>
          <button type="button" title="删除本行" aria-label="删除本行" className="ui-button ui-button--danger" disabled={lines.length === 1} onClick={() => setLines(current => current.filter(item => item.key !== line.key))}><Trash2 size={15} /></button></div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="商品名称 *"><PurchaseCatalogInput label={`商品名称 ${index + 1}`} value={line.name}
            onChange={name => update(line.key, { name, materialId: undefined, price: line.priceEdited ? line.price : "" })}
            onSelect={id => { const material = materials.find(item => item.id === id)!; update(line.key, { materialId: id, name: material.name, specification: material.specification, unit: material.unit, price: line.priceEdited ? line.price : suggestedPrice(id, resolvedSupplier) }); }}
            choices={materials.map(item => ({ id: item.id, name: item.name, detail: `${item.code} · ${item.specification || "无规格"} · ${item.unit}`, search: `${item.code} ${item.name} ${item.specification}` }))} /></Field>
          <Field label="规格"><input aria-label={`规格 ${index + 1}`} disabled={Boolean(line.materialId)} value={line.specification} onChange={event => update(line.key, { specification: event.target.value })} className={inputClass} /></Field>
          <Field label="单位 *"><input aria-label={`单位 ${index + 1}`} disabled={Boolean(line.materialId)} value={line.unit} onChange={event => update(line.key, { unit: event.target.value })} className={inputClass} /></Field>
          <Field label="数量 *"><input aria-label={`数量 ${index + 1}`} type="number" min="0" step="any" value={line.quantity} onChange={event => update(line.key, { quantity: event.target.value })} className={inputClass} /></Field>
          <Field label="采购单价（元/单位）"><input aria-label={`采购单价 ${index + 1}`} type="number" min="0" step="any" value={line.price} onChange={event => update(line.key, { price: event.target.value, priceEdited: true })} className={inputClass} /></Field>
          <Field label="行备注"><input aria-label={`行备注 ${index + 1}`} value={line.remark} onChange={event => update(line.key, { remark: event.target.value })} className={inputClass} /></Field>
        </div>
      </article>)}</div>
    </fieldset>
  </ViewportDialog>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="min-w-0 text-xs text-[#636366]"><span>{label}</span><div className="mt-1 text-[#1C1C1E]">{children}</div></div>; }
function message(error: unknown) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as Error)?.message || "采购数据操作失败"; }
