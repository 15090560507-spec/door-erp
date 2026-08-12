"use client";

import { useEffect, useState } from "react";
import ProductionDocumentActions from "./ProductionDocumentActions";
import { createShipment, getFinishedGoods, getShipments, setShipmentStatus } from "@/lib/productionApi";
import type { FinishedGood, Shipment } from "@/lib/productionTypes";

export default function ProductionShipping({ canEdit, notify }: { canEdit: boolean; notify: (message: string, error?: boolean) => void }) {
  const [goods, setGoods] = useState<FinishedGood[]>([]);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [form, setForm] = useState({ customer: '', project: '', address: '', contact: '', phone: '', logistics: '', tracking_no: '', remark: '' });
  const [busy, setBusy] = useState(false);
  const available = goods.filter((item) => item.status === '已入库');

  const load = async () => {
    try { const [finishedRows, shipmentRows] = await Promise.all([getFinishedGoods(), getShipments()]); setGoods(finishedRows); setShipments(shipmentRows); }
    catch (error) { notify(apiMessage(error, '成品和发货数据加载失败'), true); }
  };
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (action: () => Promise<unknown>, message: string) => { setBusy(true); try { await action(); await load(); notify(message); } catch (error) { notify(apiMessage(error, '操作失败'), true); } finally { setBusy(false); } };
  const submit = () => {
    if (!selected.length) return notify('请先选择至少一樘已入库成品', true);
    return run(() => createShipment({ ...form, order_ids: selected, photos: [] }), '发货单已创建');
  };

  return <div className="space-y-5">
    <section className="border border-[#E5E5EA] bg-white"><header className="border-b border-[#E5E5EA] px-5 py-4"><h2 className="font-semibold">待发货成品</h2><p className="mt-1 text-xs text-[#8E8E93]">成品质检合格并入库后，才会出现在这里。</p></header><div className="grid gap-px bg-[#E5E5EA] sm:grid-cols-2 lg:grid-cols-3">{available.map((item) => <label key={item.id} className="flex cursor-pointer gap-3 bg-white p-4"><input disabled={!canEdit} type="checkbox" checked={selected.includes(item.order_id)} onChange={(event) => setSelected(event.target.checked ? [...selected, item.order_id] : selected.filter((id) => id !== item.order_id))} /><span><strong className="block text-sm">{item.order_no}</strong><span className="mt-1 block text-xs text-[#636366]">{item.customer} · {item.project || '无项目'} · {item.finished_no}</span></span></label>)}{available.length === 0 && <div className="bg-white p-8 text-center text-sm text-[#8E8E93] sm:col-span-2 lg:col-span-3">暂无待发货成品</div>}</div></section>
    {canEdit && <section className="border border-[#E5E5EA] bg-white p-5"><h2 className="mb-4 font-semibold">创建发货单</h2><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{([['客户', 'customer'], ['项目', 'project'], ['地址', 'address'], ['联系人', 'contact'], ['电话', 'phone'], ['物流', 'logistics'], ['运单号', 'tracking_no'], ['备注', 'remark']] as const).map(([label, key]) => <label key={key} className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span><input value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} className="h-10 w-full border border-[#C7C7CC] px-3 text-sm" /></label>)}</div><button disabled={busy} onClick={submit} className="mt-4 h-10 bg-[#007AFF] px-5 text-sm text-white disabled:opacity-40">创建发货单</button></section>}
    <section className="border border-[#E5E5EA] bg-white"><header className="border-b border-[#E5E5EA] px-5 py-4"><h2 className="font-semibold">发货记录</h2></header><div className="divide-y divide-[#F2F2F7]">{shipments.map((shipment) => <div key={shipment.id} className="p-4"><div className="flex flex-wrap items-center gap-3"><strong>{shipment.shipment_no}</strong><span className="text-sm">{shipment.customer}</span><span className="bg-[#F2F2F7] px-2 py-1 text-xs">{shipment.status}</span><span className="text-xs text-[#8E8E93]">{shipment.logistics} {shipment.tracking_no}</span>{canEdit && <ProductionDocumentActions excelPath={`/production/shipments/${shipment.id}/export.xlsx`} printPath={`/production/shipments/${shipment.id}/print`} filename={`发货单_${shipment.shipment_no}`} notify={notify} />}<div className="flex-1" />{canEdit && shipment.status === '待发货' && <button disabled={busy} onClick={() => run(() => setShipmentStatus(shipment.id, '已出库', shipment.tracking_no), '发货单已出库')} className="text-sm text-[#007AFF]">确认出库</button>}{canEdit && ['已出库', '运输中'].includes(shipment.status) && <button disabled={busy} onClick={() => run(() => setShipmentStatus(shipment.id, '已完成', shipment.tracking_no), '发货流程已完成')} className="text-sm text-[#248A3D]">确认完成</button>}</div><p className="mt-2 text-sm text-[#636366]">{shipment.items.map((item) => item.order_no).join('、')}</p></div>)}{shipments.length === 0 && <div className="p-8 text-center text-sm text-[#8E8E93]">暂无发货记录</div>}</div></section>
  </div>;
}

function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string })?.userMessage || fallback; }
