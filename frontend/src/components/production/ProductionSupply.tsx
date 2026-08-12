"use client";

import { useEffect, useMemo, useState } from "react";
import ProductionDocumentActions from "./ProductionDocumentActions";
import {
  createInventoryTransaction,
  createPurchase,
  getInventory,
  getProductionMaterials,
  getPurchases,
  receivePurchase,
  setPurchaseStatus,
} from "@/lib/productionApi";
import type { InventoryBalance, ProductionMaterial, PurchaseOrder } from "@/lib/productionTypes";

interface Props {
  permissions: string[];
  notify: (message: string, error?: boolean) => void;
}

export default function ProductionSupply({ permissions, notify }: Props) {
  const [purchases, setPurchases] = useState<PurchaseOrder[]>([]);
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [materials, setMaterials] = useState<ProductionMaterial[]>([]);
  const [supplier, setSupplier] = useState("");
  const [expectedDate, setExpectedDate] = useState("");
  const [materialId, setMaterialId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [unitPrice, setUnitPrice] = useState(0);
  const [transactionType, setTransactionType] = useState("其他入库");
  const [location, setLocation] = useState("");
  const [busy, setBusy] = useState(false);

  const selectedMaterial = useMemo(
    () => materials.find((item) => item.id === Number(materialId)),
    [materialId, materials],
  );
  const canPurchase = permissions.includes("production.purchase");
  const canWarehouse = permissions.includes("production.warehouse");

  const load = async () => {
    try {
      const [purchaseRows, inventoryData, materialRows] = await Promise.all([
        getPurchases(), getInventory(), getProductionMaterials(),
      ]);
      setPurchases(purchaseRows);
      setBalances(inventoryData.balances);
      setMaterials(materialRows);
    } catch (error) {
      notify(apiMessage(error, "采购和库存数据加载失败"), true);
    }
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

  const submitPurchase = () => {
    if (!selectedMaterial || quantity <= 0) return notify("请选择物料并填写采购数量", true);
    return run(() => createPurchase({
      supplier,
      expected_date: expectedDate,
      remark: "",
      items: [{
        material_id: selectedMaterial.id,
        order_id: null,
        name: selectedMaterial.name,
        specification: selectedMaterial.specification,
        quantity,
        unit: selectedMaterial.unit,
        unit_price: unitPrice,
        remark: "",
      }],
    }), "采购单已创建");
  };

  const submitInventory = () => {
    if (!selectedMaterial || quantity <= 0) return notify("请选择物料并填写数量", true);
    return run(() => createInventoryTransaction({
      material_id: selectedMaterial.id,
      order_id: null,
      transaction_type: transactionType,
      quantity,
      unit: selectedMaterial.unit,
      warehouse_location: location,
      remark: "手工库存登记",
    }), "库存流水已登记");
  };

  const receiveAllRemaining = (purchase: PurchaseOrder) => {
    const remainingItems = purchase.items
      .map((item) => ({
        item_id: Number(item.id),
        quantity: Math.max(0, item.quantity - Number(item.received_quantity || 0)),
        warehouse_location: location,
      }))
      .filter((item) => item.quantity > 0);
    if (remainingItems.length === 0) return notify("该采购单已无待入库物料", true);
    return run(() => receivePurchase(purchase.id, remainingItems), "采购物料已入库");
  };

  return <div className="space-y-5">
    <section className="border border-[#E5E5EA] bg-white">
      <header className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] px-5 py-4"><h2 className="font-semibold">物料库存</h2><div className="flex-1" />{canWarehouse && <ProductionDocumentActions excelPath="/production/inventory/export.xlsx" printPath="/production/inventory/print" filename="库存流水" notify={notify} />}</header>
      <div className="overflow-x-auto"><table className="min-w-[720px] w-full text-sm"><thead className="bg-[#F7F7F9] text-xs text-[#636366]"><tr>{['编码', '物料', '规格', '库存数量', '单位', '仓位'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-4 py-3 text-left font-medium">{label}</th>)}</tr></thead><tbody>{balances.map((item) => <tr key={item.material_id} className="border-b border-[#F2F2F7]"><td className="px-4 py-3">{item.code}</td><td className="px-4 py-3 font-medium">{item.name}</td><td className="px-4 py-3">{materials.find((row) => row.id === item.material_id)?.specification}</td><td className="px-4 py-3 font-semibold">{item.quantity}</td><td className="px-4 py-3">{item.unit}</td><td className="px-4 py-3">{item.warehouse_location}</td></tr>)}</tbody></table>{balances.length === 0 && <Empty text="暂无生产物料，请先在生产物料中建立资料" />}</div>
    </section>

    {(canPurchase || canWarehouse) && <section className="grid gap-px border border-[#E5E5EA] bg-[#E5E5EA] lg:grid-cols-2">
      {canPurchase && <div className="bg-white p-5"><h3 className="mb-4 font-semibold">新建采购单</h3><div className="grid gap-3 sm:grid-cols-2"><MaterialSelect materials={materials} value={materialId} onChange={setMaterialId} /><Field label="供应商" value={supplier} onChange={setSupplier} /><Field type="number" label="采购数量" value={String(quantity)} onChange={(value) => setQuantity(Number(value))} /><Field type="number" label="参考单价" value={String(unitPrice)} onChange={(value) => setUnitPrice(Number(value))} /><Field type="date" label="预计到货" value={expectedDate} onChange={setExpectedDate} /><div className="flex items-end"><button disabled={busy} onClick={submitPurchase} className="h-10 w-full bg-[#007AFF] px-4 text-sm text-white disabled:opacity-40">创建采购单</button></div></div></div>}
      {canWarehouse && <div className="bg-white p-5"><h3 className="mb-4 font-semibold">库存登记</h3><div className="grid gap-3 sm:grid-cols-2"><MaterialSelect materials={materials} value={materialId} onChange={setMaterialId} /><label className="text-xs text-[#636366]"><span className="mb-1 block">类型</span><select value={transactionType} onChange={(event) => setTransactionType(event.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm">{['其他入库', '生产领料', '生产退料', '报废'].map((item) => <option key={item}>{item}</option>)}</select></label><Field type="number" label="数量" value={String(quantity)} onChange={(value) => setQuantity(Number(value))} /><Field label="仓位" value={location} onChange={setLocation} /><div className="sm:col-span-2"><button disabled={busy} onClick={submitInventory} className="h-10 w-full bg-[#007AFF] px-4 text-sm text-white disabled:opacity-40">登记库存流水</button></div></div></div>}
    </section>}

    <section className="border border-[#E5E5EA] bg-white"><header className="border-b border-[#E5E5EA] px-5 py-4"><h2 className="font-semibold">采购单</h2></header><div className="divide-y divide-[#F2F2F7]">{purchases.map((purchase) => <div key={purchase.id} className="p-4"><div className="flex flex-wrap items-center gap-3"><strong>{purchase.purchase_no}</strong><span className="text-sm text-[#636366]">{purchase.supplier || '未指定供应商'}</span><span className="bg-[#F2F2F7] px-2 py-1 text-xs">{purchase.status}</span><span className="text-xs text-[#8E8E93]">预计 {purchase.expected_date || '-'}</span>{canPurchase && <ProductionDocumentActions excelPath={`/production/purchases/${purchase.id}/export.xlsx`} printPath={`/production/purchases/${purchase.id}/print`} filename={`采购单_${purchase.purchase_no}`} notify={notify} />}<div className="flex-1" />{canPurchase && purchase.status === '草稿' && <button disabled={busy} onClick={() => run(() => setPurchaseStatus(purchase.id, '已下单'), '采购单已下单')} className="text-sm text-[#007AFF]">确认下单</button>}{canWarehouse && purchase.status !== '已完成' && purchase.items.length > 0 && <button disabled={busy} onClick={() => receiveAllRemaining(purchase)} className="text-sm text-[#248A3D]">全部到货入库</button>}</div><div className="mt-3 text-sm text-[#636366]">{purchase.items.map((item) => `${item.name} ${item.quantity}${item.unit}`).join('；')}</div></div>)}{purchases.length === 0 && <Empty text="暂无采购单" />}</div></section>
  </div>;
}

function MaterialSelect({ materials, value, onChange }: { materials: ProductionMaterial[]; value: string; onChange: (value: string) => void }) { return <label className="text-xs text-[#636366]"><span className="mb-1 block">生产物料</span><select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm"><option value="">请选择</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>; }
function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; type?: string }) { return <label className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full border border-[#C7C7CC] px-3 text-sm" /></label>; }
function Empty({ text }: { text: string }) { return <div className="p-8 text-center text-sm text-[#8E8E93]">{text}</div>; }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string })?.userMessage || fallback; }
