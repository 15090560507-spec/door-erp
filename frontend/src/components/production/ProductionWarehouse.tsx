"use client";

import { useEffect, useState } from "react";
import ProductionDocumentActions from "./ProductionDocumentActions";
import {
  createInventoryTransaction,
  getInventory,
  getMaterialRequirements,
  getProductionMaterials,
  getPurchases,
  issueOrderMaterials,
  receivePurchase,
  returnOrderMaterials,
} from "@/lib/productionApi";
import type { InventoryBalance, MaterialRequirement, ProductionMaterial, PurchaseOrder } from "@/lib/productionTypes";

export default function ProductionWarehouse({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [purchases, setPurchases] = useState<PurchaseOrder[]>([]);
  const [requirements, setRequirements] = useState<MaterialRequirement[]>([]);
  const [materials, setMaterials] = useState<ProductionMaterial[]>([]);
  const [location, setLocation] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [adjustment, setAdjustment] = useState(0);
  const [movement, setMovement] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [inventory, purchaseRows, requirementRows, materialRows] = await Promise.all([
        getInventory(), getPurchases(), getMaterialRequirements(), getProductionMaterials(),
      ]);
      setBalances(inventory.balances); setPurchases(purchaseRows); setRequirements(requirementRows); setMaterials(materialRows);
    } catch (error) { notify(apiMessage(error, "仓储数据加载失败"), true); }
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
  const receiveAll = (purchase: PurchaseOrder) => {
    const items = purchase.items.map((item) => ({ item_id: Number(item.id), quantity: Math.max(0, Number(item.quantity) - Number(item.received_quantity || 0)), warehouse_location: location })).filter((item) => item.quantity > 0);
    if (!items.length) return notify("该采购单没有待入库数量", true);
    return run(() => receivePurchase(purchase.id, items), "采购到货已入库，相关生产单已自动重新备料");
  };
  const move = (requirement: MaterialRequirement, itemId: number, kind: "issue" | "return") => {
    const quantity = Number(movement[itemId] || 0);
    if (quantity <= 0) return notify("请填写本次数量", true);
    const payload = [{ requirement_item_id: itemId, quantity, warehouse_location: location }];
    return run(
      () => kind === "issue" ? issueOrderMaterials(requirement.order_id, payload, "生产领料") : returnOrderMaterials(requirement.order_id, payload, "生产退料"),
      kind === "issue" ? "生产领料已登记" : "生产退料已登记",
    );
  };
  const adjust = () => {
    const material = materials.find((item) => item.id === Number(materialId));
    if (!material || adjustment === 0) return notify("请选择物料并填写非零调整数量", true);
    return run(() => createInventoryTransaction({ material_id: material.id, transaction_type: adjustment > 0 ? "其他入库" : "报废", quantity: Math.abs(adjustment), unit: material.unit, warehouse_location: location, remark: "手工库存调整" }), "库存调整已登记");
  };

  const pendingReceipts = purchases.filter((purchase) => purchase.status !== "已完成" && purchase.items.some((item) => Number(item.received_quantity || 0) < Number(item.quantity)));
  const activeRequirements = requirements.filter((row) => row.items.some((item) => Number(item.reserved_quantity) > 0 || Number(item.issued_quantity) > 0));

  return <div className="space-y-5">
    <section className="border border-[#E5E5EA] bg-white"><header className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] px-5 py-4"><div><h2 className="font-semibold">物料库存</h2><p className="mt-1 text-xs text-[#8E8E93]">现存为账面实物；预留已分配给生产单但尚未出库；可用可继续分配。</p></div><div className="flex-1" /><ProductionDocumentActions excelPath="/production/inventory/export.xlsx" printPath="/production/inventory/print" filename="库存流水" notify={notify} /></header><div className="overflow-x-auto"><table className="min-w-[900px] w-full text-sm"><thead className="bg-[#F7F7F9] text-xs text-[#636366]"><tr>{['编码', '物料', '规格', '现存', '已预留', '可用', '单位', '仓位'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-4 py-3 text-left font-medium">{label}</th>)}</tr></thead><tbody>{balances.map((item) => <tr key={item.material_id} className="border-b border-[#F2F2F7]"><td className="px-4 py-3">{item.code}</td><td className="px-4 py-3 font-medium">{item.name}</td><td className="px-4 py-3">{item.specification || '-'}</td><td className="px-4 py-3">{number(item.on_hand)}</td><td className="px-4 py-3 text-[#C76E00]">{number(item.reserved)}</td><td className="px-4 py-3 font-semibold text-[#248A3D]">{number(item.available)}</td><td className="px-4 py-3">{item.unit}</td><td className="px-4 py-3">{item.warehouse_location || '-'}</td></tr>)}</tbody></table>{!balances.length && <Empty text="暂无库存物料" />}</div></section>

    <section className="grid gap-px border border-[#E5E5EA] bg-[#E5E5EA] lg:grid-cols-2"><div className="bg-white p-5"><h3 className="mb-4 font-semibold">待到货入库</h3><div className="space-y-3">{pendingReceipts.map((purchase) => <div key={purchase.id} className="border border-[#E5E5EA] p-3"><div className="flex items-center gap-3"><strong className="text-sm">{purchase.purchase_no}</strong><span className="text-xs text-[#636366]">{purchase.supplier || '未指定供应商'}</span><div className="flex-1" /><button disabled={busy} onClick={() => receiveAll(purchase)} className="text-sm text-[#248A3D]">全部到货入库</button></div><p className="mt-2 text-xs text-[#8E8E93]">{purchase.items.map((item) => `${item.name} ${number(item.received_quantity || 0)}/${number(item.quantity)}${item.unit}`).join('；')}</p></div>)}{!pendingReceipts.length && <Empty text="没有待入库采购单" />}</div></div><div className="bg-white p-5"><h3 className="mb-4 font-semibold">手工库存调整</h3><div className="grid gap-3 sm:grid-cols-2"><label className="text-xs text-[#636366]"><span className="mb-1 block">物料</span><select value={materialId} onChange={(event) => setMaterialId(event.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm"><option value="">请选择</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label><Field label="仓位" value={location} onChange={setLocation} /><Field type="number" label="调整数量（正数入库，负数报废）" value={String(adjustment)} onChange={(value) => setAdjustment(Number(value))} /><div className="flex items-end"><button disabled={busy} onClick={adjust} className="h-10 w-full bg-[#007AFF] px-4 text-sm text-white disabled:opacity-40">登记库存调整</button></div></div></div></section>

    <section className="border border-[#E5E5EA] bg-white"><header className="border-b border-[#E5E5EA] px-5 py-4"><h2 className="font-semibold">生产领料与退料</h2></header><div className="divide-y divide-[#F2F2F7]">{activeRequirements.map((requirement) => <div key={requirement.id} className="p-4"><div className="mb-3 flex flex-wrap items-center gap-3"><strong>{requirement.order_no}</strong><span className="text-sm">{requirement.customer} · {requirement.project || '无项目'}</span><span className="bg-[#F2F2F7] px-2 py-1 text-xs">{requirement.status}</span></div><div className="overflow-x-auto"><table className="min-w-[840px] w-full text-sm"><thead className="text-xs text-[#636366]"><tr>{['物料', '需求', '已预留', '已领料', '本次数量', '操作'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-3 py-2 text-left font-medium">{label}</th>)}</tr></thead><tbody>{requirement.items.map((item) => <tr key={item.id}><td className="px-3 py-2">{item.name} <span className="text-[#8E8E93]">{item.specification}</span></td><td className="px-3 py-2">{number(item.required_quantity)}{item.unit}</td><td className="px-3 py-2">{number(item.reserved_quantity)}{item.unit}</td><td className="px-3 py-2">{number(item.issued_quantity)}{item.unit}</td><td className="px-3 py-2"><input type="number" min="0" value={movement[item.id] || ''} onChange={(event) => setMovement({ ...movement, [item.id]: Number(event.target.value) })} className="h-9 w-28 border border-[#C7C7CC] px-2" /></td><td className="space-x-3 px-3 py-2"><button disabled={busy || Number(item.reserved_quantity) <= 0} onClick={() => move(requirement, item.id, 'issue')} className="text-[#007AFF] disabled:text-[#C7C7CC]">领料</button><button disabled={busy || Number(item.issued_quantity) <= 0} onClick={() => move(requirement, item.id, 'return')} className="text-[#C76E00] disabled:text-[#C7C7CC]">退料</button></td></tr>)}</tbody></table></div></div>)}{!activeRequirements.length && <Empty text="暂无可领料或退料的生产单" />}</div></section>
  </div>;
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) { return <label className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full border border-[#C7C7CC] px-3 text-sm" /></label>; }
function Empty({ text }: { text: string }) { return <div className="p-8 text-center text-sm text-[#8E8E93]">{text}</div>; }
function number(value: number) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 4 }); }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string })?.userMessage || fallback; }
