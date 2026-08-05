"use client";

import { useEffect, useMemo, useState } from "react";
import ProductionDocumentActions from "./ProductionDocumentActions";
import {
  getMaterialRequirements,
  getPurchases,
  purchaseRequirementShortages,
  setPurchaseStatus,
} from "@/lib/productionApi";
import type { MaterialRequirement, PurchaseOrder } from "@/lib/productionTypes";

export default function ProductionPurchasing({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [requirements, setRequirements] = useState<MaterialRequirement[]>([]);
  const [purchases, setPurchases] = useState<PurchaseOrder[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [supplier, setSupplier] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [busy, setBusy] = useState(false);

  const shortageRows = useMemo(() => requirements.flatMap((requirement) =>
    requirement.items.filter((item) => Number(item.shortage_quantity) > 0).map((item) => ({ requirement, item }))), [requirements]);

  const load = async () => {
    try {
      const [requirementRows, purchaseRows] = await Promise.all([getMaterialRequirements(), getPurchases()]);
      setRequirements(requirementRows); setPurchases(purchaseRows);
      setSelected((value) => value.filter((id) => requirementRows.some((row) => row.items.some((item) => item.id === id && Number(item.shortage_quantity) > 0))));
    } catch (error) { notify(apiMessage(error, "采购数据加载失败"), true); }
  };
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try { await action(); await load(); notify(message); }
    catch (error) { notify(apiMessage(error, "操作失败"), true); }
    finally { setBusy(false); }
  };

  const createFromShortage = () => {
    if (!selected.length) return notify("请先选择需要采购的缺料明细", true);
    return run(() => purchaseRequirementShortages({
      supplier, expected_date: expectedDate, remark: "由 BOM 缺料自动转采购",
      items: selected.map((requirement_item_id) => ({ requirement_item_id })),
    }), "采购单已从缺料明细生成");
  };

  return <div className="space-y-5">
    <section className="border border-[#E5E5EA] bg-white">
      <header className="flex flex-wrap items-end gap-3 border-b border-[#E5E5EA] p-5">
        <div className="min-w-52 flex-1"><h2 className="font-semibold">待采购缺料</h2><p className="mt-1 text-xs text-[#8E8E93]">BOM 发布后，系统会先占用可用库存，仅把未覆盖的缺口列在这里。</p></div>
        <Field label="供应商" value={supplier} onChange={setSupplier} />
        <Field type="date" label="预计到货" value={expectedDate} onChange={setExpectedDate} />
        <button disabled={busy || !selected.length} onClick={createFromShortage} className="h-10 bg-[#007AFF] px-5 text-sm text-white disabled:opacity-40">生成采购单 ({selected.length})</button>
      </header>
      <div className="overflow-x-auto"><table className="min-w-[980px] w-full text-sm"><thead className="bg-[#F7F7F9] text-xs text-[#636366]"><tr>{['选择', '生产单号', '客户/项目', '物料编码', '物料', '规格', '需求', '已预留', '在途采购', '待采购', '状态'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-3 py-3 text-left font-medium">{label}</th>)}</tr></thead><tbody>{shortageRows.map(({ requirement, item }) => <tr key={item.id} className="border-b border-[#F2F2F7]"><td className="px-3 py-3"><input type="checkbox" disabled={!item.material_id} title={!item.material_id ? "请先在 BOM 中关联物料" : "选择采购缺口"} checked={selected.includes(item.id)} onChange={(event) => setSelected(event.target.checked ? [...selected, item.id] : selected.filter((id) => id !== item.id))} /></td><td className="px-3 py-3 font-medium text-[#007AFF]">{requirement.order_no}</td><td className="px-3 py-3">{requirement.customer}<span className="ml-1 text-[#8E8E93]">{requirement.project}</span></td><td className="px-3 py-3">{item.material_code || <span className="text-[#FF3B30]">先关联物料</span>}</td><td className="px-3 py-3">{item.name}</td><td className="px-3 py-3">{item.specification || '-'}</td><td className="px-3 py-3">{number(item.required_quantity)}{item.unit}</td><td className="px-3 py-3">{number(item.reserved_quantity)}{item.unit}</td><td className="px-3 py-3">{number(Number(item.purchased_quantity) - Number(item.received_quantity))}{item.unit}</td><td className="px-3 py-3 font-semibold text-[#FF3B30]">{number(item.shortage_quantity)}{item.unit}</td><td className="px-3 py-3">{item.status}</td></tr>)}</tbody></table>{!shortageRows.length && <Empty text="当前没有未覆盖的采购缺口" />}</div>
    </section>

    <section className="border border-[#E5E5EA] bg-white"><header className="border-b border-[#E5E5EA] px-5 py-4"><h2 className="font-semibold">采购单</h2></header><div className="divide-y divide-[#F2F2F7]">{purchases.map((purchase) => <div key={purchase.id} className="p-4"><div className="flex flex-wrap items-center gap-3"><strong>{purchase.purchase_no}</strong><span className="text-sm text-[#636366]">{purchase.supplier || '未指定供应商'}</span><span className="bg-[#F2F2F7] px-2 py-1 text-xs">{purchase.status}</span><span className="text-xs text-[#8E8E93]">预计 {purchase.expected_date || '-'}</span><ProductionDocumentActions excelPath={`/production/purchases/${purchase.id}/export.xlsx`} printPath={`/production/purchases/${purchase.id}/print`} filename={`采购单_${purchase.purchase_no}`} notify={notify} /><div className="flex-1" />{purchase.status === '草稿' && <button disabled={busy} onClick={() => run(() => setPurchaseStatus(purchase.id, '已下单'), '采购单已确认下单')} className="text-sm text-[#007AFF]">确认下单</button>}</div><div className="mt-3 text-sm text-[#636366]">{purchase.items.map((item) => `${item.name} ${number(item.received_quantity || 0)}/${number(item.quantity)}${item.unit}`).join('；')}</div></div>)}{!purchases.length && <Empty text="暂无采购单" />}</div></section>
  </div>;
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) { return <label className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-44 border border-[#C7C7CC] px-3 text-sm" /></label>; }
function Empty({ text }: { text: string }) { return <div className="p-10 text-center text-sm text-[#8E8E93]">{text}</div>; }
function number(value: number) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 4 }); }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string })?.userMessage || fallback; }
