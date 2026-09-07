"use client";

import { useEffect, useMemo, useState } from "react";
import ProductionDocumentActions from "./ProductionDocumentActions";
import ProductionTimeline from "./ProductionTimeline";
import {
  copyProductionOrder,
  createCuttingSheet,
  createQuality,
  getBom,
  getCuttingSheet,
  getFinishedGoods,
  getOrderMaterialRequirement,
  getOperations,
  getProductionMaterials,
  getQuality,
  getSchedule,
  getProductionTimeline,
  inboundFinishedGood,
  issueOrderMaterials,
  orderAction,
  publishBom,
  saveBom,
  saveCuttingSheet,
  saveOperation,
  saveSchedule,
  returnOrderMaterials,
  withdrawProductionOrder,
  downloadProductionFile,
} from "@/lib/productionApi";
import type {
  BomData,
  BomItem,
  CuttingSheet,
  FinishedGood,
  MaterialRequirement,
  ProductionOperation,
  ProductionMaterial,
  ProductionOrder,
  ProductionSchedule,
  ProductionTimelineItem,
  QualityInspection,
} from "@/lib/productionTypes";

const emptyBomItem: BomItem = {
  category: "其他", name: "", specification: "", material: "", thickness: "",
  quantity: 1, unit: "", supply_type: "自制", remark: "",
};

interface Props {
  order: ProductionOrder;
  permissions: string[];
  notify: (message: string, error?: boolean) => void;
  onChanged: () => void;
}

export default function ProductionOrderDetail({ order, permissions, notify, onChanged }: Props) {
  const [tab, setTab] = useState("snapshot");
  const [bom, setBom] = useState<BomData | null>(null);
  const [cutting, setCutting] = useState<CuttingSheet | null>(null);
  const [schedule, setSchedule] = useState<ProductionSchedule | null>(null);
  const [operations, setOperations] = useState<ProductionOperation[]>([]);
  const [quality, setQuality] = useState<QualityInspection[]>([]);
  const [finished, setFinished] = useState<FinishedGood | null>(null);
  const [requirement, setRequirement] = useState<MaterialRequirement | null>(null);
  const [materials, setMaterials] = useState<ProductionMaterial[]>([]);
  const [timeline, setTimeline] = useState<ProductionTimelineItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"withdraw" | "void" | null>(null);

  const can = (permission: string) => permissions.includes(permission);
  const load = async () => {
    try {
      const [bomData, cuttingData, scheduleData, operationData, qualityData, finishedData, timelineData, requirementData, materialData] = await Promise.all([
        getBom(order.id), getCuttingSheet(order.id), getSchedule(order.id), getOperations(order.id),
        getQuality(order.id), getFinishedGoods(), getProductionTimeline(order.id),
        getOrderMaterialRequirement(order.id), getProductionMaterials(),
      ]);
      setBom(bomData); setCutting(cuttingData); setSchedule(scheduleData); setOperations(operationData);
      setQuality(qualityData); setFinished(finishedData.find((item) => item.order_id === order.id) || null);
      setTimeline(timelineData);
      setRequirement(requirementData); setMaterials(materialData);
    } catch (error) { notify(apiMessage(error, "生产订单明细加载失败"), true); }
  };
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [order.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try { await action(); await load(); onChanged(); notify(success); }
    catch (error) { notify(apiMessage(error, "操作失败"), true); }
    finally { setBusy(false); }
  };

  return (
    <section className="border border-[#D1D1D6] bg-white">
      <header className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] px-5 py-4">
        <div className="min-w-56 flex-1">
          <div className="text-xs text-[#8E8E93]">生产订单</div>
          <h2 className="text-lg font-semibold text-[#1C1C1E]">{order.order_no} · {order.customer}</h2>
          <p className="mt-1 text-xs text-[#636366]">{order.project || '无项目名称'} · {order.stage} · {order.status}</p>
        </div>
        {can('production.sales') && <button disabled={busy} onClick={() => run(() => copyProductionOrder(order.id), '已复制为新的生产订单')} className="h-9 border border-[#C7C7CC] px-3 text-sm">复制订单</button>}
        <button disabled={busy} onClick={() => void run(() => downloadProductionFile(`/production/orders/${order.id}/approved-dxf`, `${order.order_no}_终审冻结版.dxf`), '终审冻结版图纸已下载')} className="h-9 border border-[#C7C7CC] px-3 text-sm">下载终审 DXF</button>
        {can('production.sales') && !order.cutting_started && order.status === '进行中' && <button disabled={busy} onClick={() => setConfirmAction('withdraw')} className="h-9 border border-[#FF3B30] px-3 text-sm text-[#FF3B30]">撤回</button>}
        {can('production.manager') && order.status === '进行中' && <button disabled={busy} onClick={() => run(() => orderAction(order.id, 'pause', '生产暂停'), '生产订单已暂停')} className="h-9 border border-[#C7C7CC] px-3 text-sm">暂停</button>}
        {can('production.manager') && order.status === '已暂停' && <button disabled={busy} onClick={() => run(() => orderAction(order.id, 'resume'), '生产订单已恢复')} className="h-9 bg-[#007AFF] px-3 text-sm text-white">恢复</button>}
        {can('production.manager') && !['已作废', '已完成'].includes(order.status) && <button disabled={busy} onClick={() => setConfirmAction('void')} className="h-9 border border-[#FF3B30] px-3 text-sm text-[#FF3B30]">作废</button>}
      </header>

      <OrderSummary bom={bom} requirement={requirement} cutting={cutting} schedule={schedule} operations={operations} quality={quality} finished={finished} />

      <nav className="flex overflow-x-auto border-b border-[#E5E5EA] bg-[#FAFAFC]">
        {[['snapshot', '订单快照'], ['timeline', '全过程记录'], ['bom', '手工 BOM'], ['materials', '物料需求与领料'], ['cutting', '下料与排单'], ['operations', '生产与质检']].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={`h-11 whitespace-nowrap border-b-2 px-5 text-sm ${tab === key ? 'border-[#007AFF] text-[#007AFF]' : 'border-transparent text-[#636366]'}`}>{label}</button>
        ))}
      </nav>

      <div className="p-5">
        {tab === 'snapshot' && <Snapshot order={order} />}
        {tab === 'timeline' && <ProductionTimeline items={timeline} />}
        {tab === 'bom' && bom && <BomEditor orderId={order.id} bom={bom} materials={materials} canEdit={can('production.technical')} busy={busy} notify={notify} setBom={setBom} onSave={() => run(() => saveBom(order.id, bom.items), 'BOM 草稿已保存')} onPublish={() => run(() => publishBom(order.id), 'BOM 已发布并生成物料需求')} />}
        {tab === 'materials' && <MaterialRequirementPanel requirement={requirement} busy={busy} canWarehouse={can('production.warehouse')} onIssue={(itemId, quantity) => run(() => issueOrderMaterials(order.id, [{ requirement_item_id: itemId, quantity }], '订单详情领料'), '生产领料已登记')} onReturn={(itemId, quantity) => run(() => returnOrderMaterials(order.id, [{ requirement_item_id: itemId, quantity }], '订单详情退料'), '生产退料已登记')} />}
        {tab === 'cutting' && <CuttingAndSchedule orderId={order.id} cutting={cutting} schedule={schedule} canCut={can('production.cutting') || can('production.technical')} canSchedule={can('production.schedule')} busy={busy} notify={notify} setCutting={setCutting} setSchedule={setSchedule} create={() => run(() => createCuttingSheet(order.id), '综合下料单已生成')} saveCutting={() => cutting && run(() => saveCuttingSheet(order.id, cutting), '综合下料单已保存')} savePlan={() => schedule && run(() => saveSchedule(order.id, stripSchedule(schedule)), '排单已保存')} />}
        {tab === 'operations' && <OperationsAndQuality orderId={order.id} operations={operations} inspections={quality} finished={finished} canWork={can('production.worker') || can('production.manager')} canQuality={can('production.quality')} canWarehouse={can('production.warehouse')} busy={busy} notify={notify} updateOperation={(operation, status) => run(() => saveOperation(order.id, operation.id, { status, operator_name: operation.operator_name, remark: operation.remark }), `${operation.name} 已更新`)} submitQuality={(result, inspector, returnOperation, remark) => run(() => createQuality(order.id, { result, inspector, return_operation: returnOperation, photos: [], remark }), `质检结果已保存：${result}`)} inbound={(location) => run(() => inboundFinishedGood(order.id, location), '成品已入库')} />}
      </div>
      {confirmAction && <ConfirmDialog title={confirmAction === 'withdraw' ? '确认撤回生产订单' : '确认作废生产订单'} detail={confirmAction === 'withdraw' ? '撤回后该订单将停止后续生产流转。' : '作废属于高风险操作，订单将不能继续生产。'} busy={busy} onCancel={() => setConfirmAction(null)} onConfirm={() => { const action = confirmAction; setConfirmAction(null); void run(action === 'withdraw' ? () => withdrawProductionOrder(order.id, '销售确认撤回') : () => orderAction(order.id, 'void', '管理人员确认作废'), action === 'withdraw' ? '生产订单已撤回' : '生产订单已作废'); }} />}
    </section>
  );
}

function Snapshot({ order }: { order: ProductionOrder }) {
  const task = order.task_snapshot || {};
  const params = (task.params || {}) as Record<string, unknown>;
  const rows = [
    ['订货单位', order.customer], ['项目名称', order.project || '-'], ['要求交期', order.due_date || '-'],
    ['门型', params.door_type], ['洞口尺寸', `${params.dw || '-'} × ${params.dh || '-'}`],
    ['开向', `${params.sel_kx || ''}${params.sel_nk || ''}`], ['制作材料', params.zzcl],
    ['正面款式', params.zmks], ['反面款式', params.fmks], ['销售备注', order.sales_note || '-'],
  ];
  return <div className="grid border-l border-t border-[#E5E5EA] sm:grid-cols-2 lg:grid-cols-3">{rows.map(([label, value]) => <div key={String(label)} className="border-b border-r border-[#E5E5EA] p-3"><div className="text-xs text-[#8E8E93]">{String(label)}</div><div className="mt-1 min-h-5 break-words text-sm">{String(value || '-')}</div></div>)}</div>;
}

function OrderSummary({ bom, requirement, cutting, schedule, operations, quality, finished }: { bom: BomData | null; requirement: MaterialRequirement | null; cutting: CuttingSheet | null; schedule: ProductionSchedule | null; operations: ProductionOperation[]; quality: QualityInspection[]; finished: FinishedGood | null }) {
  const completed = operations.filter((item) => ['已完成', '不适用'].includes(item.status)).length;
  const rows = [
    ['BOM', bom ? `${bom.status.status} · ${bom.items.length} 项` : '未建立'],
    ['备料', requirement ? `${requirement.status} · ${requirement.items.length} 项` : '未生成'],
    ['下料', cutting ? `${cutting.status} · ${cutting.items.filter((item) => item.completed).length}/${cutting.items.length}` : '未生成'],
    ['排单', schedule?.planned_end ? `${schedule.owner || schedule.producer || '未指定'} · ${schedule.planned_end}` : '未排单'],
    ['生产', `${completed}/${operations.length || 0} 道工序`],
    ['质检', quality[0]?.result || '未质检'],
    ['成品', finished ? `已入库 · ${finished.warehouse_location || '未指定仓位'}` : '未入库'],
  ];
  return <div className="grid gap-px border-b border-[#E5E5EA] bg-[#E5E5EA] sm:grid-cols-3 xl:grid-cols-7">{rows.map(([label, value]) => <div key={label} className="bg-white px-4 py-3"><span className="block text-xs text-[#8E8E93]">{label}</span><strong className="mt-1 block truncate text-sm" title={value}>{value}</strong></div>)}</div>;
}

function BomEditor({ orderId, bom, materials, canEdit, busy, notify, setBom, onSave, onPublish }: { orderId: number; bom: BomData; materials: ProductionMaterial[]; canEdit: boolean; busy: boolean; notify: (message: string, error?: boolean) => void; setBom: (bom: BomData) => void; onSave: () => void; onPublish: () => void }) {
  const published = bom.status.status === '已发布';
  const update = (index: number, field: keyof BomItem, value: string | number) => setBom({ ...bom, items: bom.items.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item) });
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center gap-3"><span className={`px-2 py-1 text-xs ${published ? 'bg-[#E7F7EA] text-[#248A3D]' : 'bg-[#FFF4D6] text-[#9A6700]'}`}>{bom.status.status}</span><ProductionDocumentActions excelPath={`/production/orders/${orderId}/documents/bom.xlsx`} printPath={`/production/orders/${orderId}/documents/bom/print`} filename={`BOM_${orderId}`} disabled={!bom.items.length} notify={notify} /><div className="flex-1" />{canEdit && !published && <><button onClick={() => setBom({ ...bom, items: [...bom.items, { ...emptyBomItem }] })} className="h-9 border border-[#C7C7CC] px-3 text-sm">新增材料</button><button disabled={busy} onClick={onSave} className="h-9 bg-[#007AFF] px-4 text-sm text-white">保存草稿</button><button disabled={busy} onClick={onPublish} className="h-9 bg-[#248A3D] px-4 text-sm text-white">发布 BOM</button></>}</div>
    <div className="overflow-x-auto border border-[#E5E5EA]"><table className="min-w-[1220px] w-full text-sm"><thead className="bg-[#F7F7F9] text-xs text-[#636366]"><tr>{['物料资料', '分类', '名称', '规格', '材质', '厚度', '数量', '单位', '来源', '备注', ''].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-2 py-2 text-left font-medium">{label}</th>)}</tr></thead><tbody>{bom.items.map((item, index) => <tr key={item.id || index} className="border-b border-[#F2F2F7]">
      <td className="px-2 py-2"><select disabled={published || !canEdit} value={item.material_id || ''} onChange={(event) => { const selected = materials.find((row) => row.id === Number(event.target.value)); setBom({ ...bom, items: bom.items.map((row, rowIndex) => rowIndex === index ? { ...row, material_id: selected?.id || null, category: selected?.category || row.category, name: selected?.name || row.name, specification: selected?.specification || row.specification, material: selected?.material || row.material, thickness: selected?.thickness || row.thickness, unit: selected?.unit || row.unit } : row) }); }} className="h-9 w-44 border border-[#D1D1D6] bg-white px-2 text-xs disabled:bg-[#F7F7F9]"><option value="">未关联库存物料</option>{materials.map((material) => <option key={material.id} value={material.id}>{material.code} · {material.name}</option>)}</select></td><CellInput value={item.category} disabled={published || !canEdit} onChange={(value) => update(index, 'category', value)} /><CellInput value={item.name} disabled={published || !canEdit} onChange={(value) => update(index, 'name', value)} /><CellInput value={item.specification} disabled={published || !canEdit} onChange={(value) => update(index, 'specification', value)} /><CellInput value={item.material} disabled={published || !canEdit} onChange={(value) => update(index, 'material', value)} /><CellInput value={item.thickness} disabled={published || !canEdit} onChange={(value) => update(index, 'thickness', value)} /><CellInput type="number" value={item.quantity} disabled={published || !canEdit} onChange={(value) => update(index, 'quantity', Number(value))} /><CellInput value={item.unit} disabled={published || !canEdit} onChange={(value) => update(index, 'unit', value)} /><CellInput value={item.supply_type} disabled={published || !canEdit} onChange={(value) => update(index, 'supply_type', value)} /><CellInput value={item.remark} disabled={published || !canEdit} onChange={(value) => update(index, 'remark', value)} />
      <td className="px-2 py-2">{canEdit && !published && <button onClick={() => setBom({ ...bom, items: bom.items.filter((_, itemIndex) => itemIndex !== index) })} className="text-[#FF3B30]">删除</button>}</td>
    </tr>)}</tbody></table>{bom.items.length === 0 && <div className="p-8 text-center text-sm text-[#8E8E93]">BOM 还是空的，请新增材料</div>}</div>
  </div>;
}

function MaterialRequirementPanel({ requirement, busy, canWarehouse, onIssue, onReturn }: { requirement: MaterialRequirement | null; busy: boolean; canWarehouse: boolean; onIssue: (itemId: number, quantity: number) => void; onReturn: (itemId: number, quantity: number) => void }) {
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  if (!requirement) return <div className="border border-dashed border-[#C7C7CC] p-10 text-center text-sm text-[#8E8E93]">发布 BOM 后，系统会在这里生成物料需求并自动占用可用库存。</div>;
  return <div className="space-y-4"><div className="flex flex-wrap items-center gap-3"><h3 className="font-semibold">物料需求</h3><span className={`px-2 py-1 text-xs ${['已备料', '已领料'].includes(requirement.status) ? 'bg-[#E7F7EA] text-[#248A3D]' : 'bg-[#FFF0EF] text-[#FF3B30]'}`}>{requirement.status}</span><span className="text-sm text-[#636366]">现存只在领料时扣减；预留不会改变实物库存。</span></div><div className="overflow-x-auto border border-[#E5E5EA]"><table className="min-w-[1080px] w-full text-sm"><thead className="bg-[#F7F7F9] text-xs text-[#636366]"><tr>{['编码', '物料', '规格', '需求', '预留', '已采购', '已到货', '已领料', '待采购', '状态', '本次数量', '操作'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-3 py-3 text-left font-medium">{label}</th>)}</tr></thead><tbody>{requirement.items.map((item) => <tr key={item.id} className="border-b border-[#F2F2F7]"><td className="px-3 py-3">{item.material_code || <span className="text-[#FF3B30]">未关联</span>}</td><td className="px-3 py-3 font-medium">{item.name}</td><td className="px-3 py-3">{item.specification || '-'}</td><td className="px-3 py-3">{amount(item.required_quantity)}{item.unit}</td><td className="px-3 py-3">{amount(item.reserved_quantity)}{item.unit}</td><td className="px-3 py-3">{amount(item.purchased_quantity)}{item.unit}</td><td className="px-3 py-3">{amount(item.received_quantity)}{item.unit}</td><td className="px-3 py-3">{amount(item.issued_quantity)}{item.unit}</td><td className="px-3 py-3 font-semibold text-[#FF3B30]">{amount(item.shortage_quantity)}{item.unit}</td><td className="px-3 py-3">{item.status}</td><td className="px-3 py-3"><input type="number" min="0" value={quantities[item.id] || ''} onChange={(event) => setQuantities({ ...quantities, [item.id]: Number(event.target.value) })} className="h-9 w-24 border border-[#C7C7CC] px-2" /></td><td className="whitespace-nowrap px-3 py-3"><button disabled={busy || !canWarehouse || Number(item.reserved_quantity) <= 0} onClick={() => onIssue(item.id, Number(quantities[item.id] || 0))} className="mr-3 text-[#007AFF] disabled:text-[#C7C7CC]">领料</button><button disabled={busy || !canWarehouse || Number(item.issued_quantity) <= 0} onClick={() => onReturn(item.id, Number(quantities[item.id] || 0))} className="text-[#C76E00] disabled:text-[#C7C7CC]">退料</button></td></tr>)}</tbody></table></div></div>;
}

function CuttingAndSchedule({ orderId, cutting, schedule, canCut, canSchedule, busy, notify, setCutting, setSchedule, create, saveCutting, savePlan }: { orderId: number; cutting: CuttingSheet | null; schedule: ProductionSchedule | null; canCut: boolean; canSchedule: boolean; busy: boolean; notify: (message: string, error?: boolean) => void; setCutting: (sheet: CuttingSheet) => void; setSchedule: (schedule: ProductionSchedule) => void; create: () => void; saveCutting: () => void; savePlan: () => void }) {
  const plan = schedule || { order_id: orderId, planned_start: '', planned_end: '', producer: '', shortage_status: '未知', owner: '', allow_shortage: false };
  return <div className="space-y-6">
    <section><div className="mb-3 flex flex-wrap items-center gap-3"><h3 className="font-semibold">综合下料单</h3>{cutting && <ProductionDocumentActions excelPath={`/production/orders/${orderId}/documents/cutting.xlsx`} printPath={`/production/orders/${orderId}/documents/cutting/print`} filename={`综合下料单_${orderId}`} notify={notify} />}<div className="flex-1" />{!cutting && canCut && <button disabled={busy} onClick={create} className="h-9 bg-[#007AFF] px-4 text-sm text-white">从已发布 BOM 生成</button>}{cutting && canCut && <button disabled={busy} onClick={saveCutting} className="h-9 bg-[#007AFF] px-4 text-sm text-white">保存下料单</button>}</div>
      {cutting ? <div className="overflow-x-auto border border-[#E5E5EA]"><div className="flex items-center gap-3 border-b border-[#E5E5EA] bg-[#F7F7F9] p-3"><span className="text-sm">状态</span><select disabled={!canCut} value={cutting.status} onChange={(e) => setCutting({ ...cutting, status: e.target.value })} className="h-9 border border-[#C7C7CC] bg-white px-3 text-sm">{['草稿', '已下发', '下料中', '已完成'].map((item) => <option key={item}>{item}</option>)}</select></div><table className="min-w-[800px] w-full text-sm"><thead className="bg-[#FAFAFC] text-xs"><tr>{['材料', '规格', '理论数量', '实际数量', '单位', '下料人', '完成', '备注'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-2 py-2 text-left font-medium">{label}</th>)}</tr></thead><tbody>{cutting.items.map((item, index) => <tr key={item.id} className="border-b border-[#F2F2F7]"><td className="px-2 py-2">{item.name}</td><td className="px-2 py-2">{item.specification}</td><td className="px-2 py-2">{item.quantity}</td><CellInput type="number" disabled={!canCut} value={item.actual_quantity} onChange={(value) => setCutting({ ...cutting, items: cutting.items.map((row, rowIndex) => rowIndex === index ? { ...row, actual_quantity: Number(value) } : row) })} /><td className="px-2 py-2">{item.unit}</td><CellInput disabled={!canCut} value={item.cutter} onChange={(value) => setCutting({ ...cutting, items: cutting.items.map((row, rowIndex) => rowIndex === index ? { ...row, cutter: value } : row) })} /><td className="px-2 py-2"><input disabled={!canCut} type="checkbox" checked={Boolean(item.completed)} onChange={(e) => setCutting({ ...cutting, items: cutting.items.map((row, rowIndex) => rowIndex === index ? { ...row, completed: e.target.checked ? 1 : 0 } : row) })} /></td><CellInput disabled={!canCut} value={item.remark} onChange={(value) => setCutting({ ...cutting, items: cutting.items.map((row, rowIndex) => rowIndex === index ? { ...row, remark: value } : row) })} /></tr>)}</tbody></table></div> : <div className="border border-dashed border-[#C7C7CC] p-8 text-center text-sm text-[#8E8E93]">尚未生成综合下料单</div>}
    </section>
    <section><div className="mb-3 flex items-center"><h3 className="font-semibold">排单</h3><div className="flex-1" />{canSchedule && <button disabled={busy} onClick={savePlan} className="h-9 bg-[#007AFF] px-4 text-sm text-white">保存排单</button>}</div><div className="grid gap-3 border border-[#E5E5EA] p-4 sm:grid-cols-2 lg:grid-cols-6"><LabeledInput type="date" label="计划开始日期" value={plan.planned_start} disabled={!canSchedule} onChange={(value) => setSchedule({ ...plan, planned_start: value })} /><LabeledInput type="date" label="计划完成日期" value={plan.planned_end} disabled={!canSchedule} onChange={(value) => setSchedule({ ...plan, planned_end: value })} /><LabeledInput label="生产人" value={plan.producer} disabled={!canSchedule} onChange={(value) => setSchedule({ ...plan, producer: value })} /><label className="text-xs text-[#636366]"><span className="mb-1 block">系统缺料状态</span><input readOnly value={plan.shortage_status} className="h-10 w-full border border-[#C7C7CC] bg-[#F7F7F9] px-3 text-sm" /></label><LabeledInput label="负责人" value={plan.owner} disabled={!canSchedule} onChange={(value) => setSchedule({ ...plan, owner: value })} /><label className="flex items-end gap-2 pb-2 text-sm"><input disabled={!canSchedule} type="checkbox" checked={Boolean(plan.allow_shortage)} onChange={(event) => setSchedule({ ...plan, allow_shortage: event.target.checked })} />允许缺料排单</label></div></section>
  </div>;
}

function OperationsAndQuality({ orderId, operations, inspections, finished, canWork, canQuality, canWarehouse, busy, notify, updateOperation, submitQuality, inbound }: { orderId: number; operations: ProductionOperation[]; inspections: QualityInspection[]; finished: FinishedGood | null; canWork: boolean; canQuality: boolean; canWarehouse: boolean; busy: boolean; notify: (message: string, error?: boolean) => void; updateOperation: (operation: ProductionOperation, status: string) => void; submitQuality: (result: string, inspector: string, returnOperation: string, remark: string) => void; inbound: (location: string) => void }) {
  const [inspector, setInspector] = useState(''); const [returnOperation, setReturnOperation] = useState(''); const [remark, setRemark] = useState(''); const [location, setLocation] = useState('');
  const allDone = useMemo(() => operations.length > 0 && operations.every((item) => ['已完成', '不适用'].includes(item.status)), [operations]);
  const latestPass = inspections[0]?.result === '合格';
  return <div className="space-y-6"><section><h3 className="mb-3 font-semibold">固定生产工序</h3><div className="grid gap-px border border-[#E5E5EA] bg-[#E5E5EA] sm:grid-cols-2 lg:grid-cols-4">{operations.map((operation) => <div key={operation.id} className="bg-white p-4"><div className="flex items-center gap-2"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#F2F2F7] text-xs">{operation.sequence_no}</span><strong className="text-sm">{operation.name}</strong></div><select disabled={!canWork || busy} value={operation.status} onChange={(e) => updateOperation(operation, e.target.value)} className="mt-3 h-9 w-full border border-[#C7C7CC] bg-white px-2 text-sm">{['待开始', '进行中', '已完成', '不适用'].map((item) => <option key={item}>{item}</option>)}</select></div>)}</div></section>
    <section className="border-t border-[#E5E5EA] pt-5"><div className="mb-3 flex flex-wrap items-center gap-3"><h3 className="font-semibold">成品质检</h3>{inspections.length > 0 && <ProductionDocumentActions excelPath={`/production/orders/${orderId}/documents/quality.xlsx`} printPath={`/production/orders/${orderId}/documents/quality/print`} filename={`质检单_${orderId}`} notify={notify} />}</div>{canQuality && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><LabeledInput label="质检人" value={inspector} onChange={setInspector} /><label className="text-xs text-[#636366]"><span className="mb-1 block">退回工序</span><select value={returnOperation} onChange={(e) => setReturnOperation(e.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm"><option value="">不退回</option>{operations.map((item) => <option key={item.id}>{item.name}</option>)}</select></label><LabeledInput label="备注" value={remark} onChange={setRemark} /><div className="flex items-end gap-2"><button disabled={busy || !allDone || !inspector} onClick={() => submitQuality('合格', inspector, '', remark)} className="h-10 flex-1 bg-[#248A3D] px-3 text-sm text-white disabled:opacity-40">合格</button><button disabled={busy || !inspector || !returnOperation} onClick={() => submitQuality('不合格', inspector, returnOperation, remark)} className="h-10 flex-1 bg-[#FF3B30] px-3 text-sm text-white disabled:opacity-40">不合格</button></div></div>}<div className="mt-3 space-y-2">{inspections.map((item) => <div key={item.id} className="flex flex-wrap gap-3 border-b border-[#F2F2F7] py-2 text-sm"><strong className={item.result === '合格' ? 'text-[#248A3D]' : 'text-[#FF3B30]'}>{item.result}</strong><span>{item.inspector}</span><span className="text-[#8E8E93]">{item.created_at}</span><span>{item.remark}</span></div>)}</div></section>
    <section className="border-t border-[#E5E5EA] pt-5"><h3 className="mb-3 font-semibold">成品入库</h3>{finished ? <div className="bg-[#E7F7EA] p-3 text-sm text-[#248A3D]">已入库：{finished.finished_no} · {finished.warehouse_location || '未指定仓位'}</div> : <div className="flex max-w-lg gap-2"><input disabled={!canWarehouse} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="成品仓位" className="h-10 flex-1 border border-[#C7C7CC] px-3 text-sm" /><button disabled={!canWarehouse || !latestPass || busy} onClick={() => inbound(location)} className="h-10 bg-[#007AFF] px-4 text-sm text-white disabled:opacity-40">办理入库</button></div>}</section>
  </div>;
}

function ConfirmDialog({ title, detail, busy, onCancel, onConfirm }: { title: string; detail: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <div className="ui-dialog-backdrop" onClick={onCancel}>
    <div className="ui-dialog" onClick={(event) => event.stopPropagation()}>
      <div className="ui-dialog__header"><h3 className="ui-dialog__title">{title}</h3></div>
      <div className="ui-dialog__body"><p className="text-sm leading-6 text-[#636366]">{detail}</p></div>
      <div className="ui-dialog__footer"><button disabled={busy} onClick={onCancel} className="ui-button ui-button--secondary">取消</button><button disabled={busy} onClick={onConfirm} className="ui-button ui-button--danger">确认执行</button></div>
    </div>
  </div>;
}

function CellInput({ value, onChange, disabled = false, type = 'text' }: { value: string | number; onChange: (value: string) => void; disabled?: boolean; type?: string }) { return <td className="px-1 py-1"><input type={type} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className="h-9 w-full min-w-20 border border-transparent bg-transparent px-2 outline-none enabled:hover:border-[#C7C7CC] enabled:focus:border-[#007AFF] disabled:text-[#1C1C1E]" /></td>; }
function LabeledInput({ label, value, onChange, disabled = false, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean; type?: string }) { return <label className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span><input type={type} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm disabled:bg-[#F7F7F9]" /></label>; }
function stripSchedule(schedule: ProductionSchedule) { return { planned_start: schedule.planned_start, planned_end: schedule.planned_end, producer: schedule.producer, shortage_status: schedule.shortage_status, owner: schedule.owner, allow_shortage: Boolean(schedule.allow_shortage) }; }
function amount(value: number) { return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 4 }); }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string })?.userMessage || fallback; }
