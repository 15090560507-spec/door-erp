"use client";

import { Calculator, CheckCheck, Copy, Plus, Save, Send, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import NoticeDialog from "@/components/door-cad/NoticeDialog";
import StatusChip from "@/components/workspace/StatusChip";
import { apiErrorMessage } from "@/lib/api";
import { getDoorBom } from "@/lib/bomApi";
import type { BomRow } from "@/lib/bomTypes";
import {
  getFulfillmentCalculation,
  initializeFulfillmentCalculation,
  publishFulfillmentCalculation,
  saveFulfillmentCalculation,
  submitFulfillmentCalculation,
} from "@/lib/fulfillmentApi";
import type { FulfillmentCalculation, FulfillmentCalculationItem } from "@/lib/fulfillmentTypes";

type Props = {
  doorId: number;
  refreshKey?: number;
  onPublished?: () => Promise<void> | void;
};

let temporaryId = -1;

function newItem(component: BomRow, source?: FulfillmentCalculationItem): FulfillmentCalculationItem {
  return {
    id: temporaryId--,
    component_id: component.id,
    component_name: component.name,
    component_category: component.category,
    component_group_code: component.group_code,
    part_name: source ? `${source.part_name}（复制）` : component.name,
    material_specification: source?.material_specification || component.specification || "",
    finished_size: source?.finished_size || component.specification || "",
    cut_length: source?.cut_length || 0,
    cut_width: source?.cut_width || 0,
    quantity: source?.quantity || component.planned_quantity || component.quantity || 1,
    unit: source?.unit || component.unit || "件",
    waste_rate: source?.waste_rate || component.waste_rate || 0,
    actual_material_quantity: source?.actual_material_quantity || component.planned_quantity || component.quantity || 1,
    grain_direction: source?.grain_direction || "",
    cutting_method: source?.cutting_method || "",
    source_type: "manual",
    remark: source?.remark || "",
  };
}

export default function CalculationWorkbench({ doorId, refreshKey = 0, onPublished }: Props) {
  const [calculation, setCalculation] = useState<FulfillmentCalculation | null>(null);
  const [components, setComponents] = useState<BomRow[]>([]);
  const [items, setItems] = useState<FulfillmentCalculationItem[]>([]);
  const [deletedIds, setDeletedIds] = useState<number[]>([]);
  const [remark, setRemark] = useState("");
  const [bomPublished, setBomPublished] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ title: string; message: string; error?: boolean } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [bom, current] = await Promise.all([getDoorBom(doorId), getFulfillmentCalculation(doorId)]);
      setComponents(bom.rows);
      setBomPublished(bom.status === "已确认");
      setCalculation(current);
      setItems(current?.items || []);
      setRemark(current?.remark || "");
      setDeletedIds([]);
    } catch (error) {
      setNotice({ title: "算料加载失败", message: apiErrorMessage(error, "无法读取算料数据"), error: true });
    } finally {
      setLoading(false);
    }
  }, [doorId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load, refreshKey]);

  const selectableComponents = useMemo(
    () => components.filter((row) => row.procurement_mode === "make" && row.item_kind !== "assembly"),
    [components],
  );
  const editable = Boolean(calculation && calculation.status !== "已发布");
  const updateItem = (index: number, patch: Partial<FulfillmentCalculationItem>) => setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  const persist = async () => {
    const result = await saveFulfillmentCalculation(doorId, {
      items: items.map((item) => ({ ...item, id: item.id && item.id > 0 ? item.id : undefined })),
      delete_item_ids: deletedIds,
      remark,
    });
    setCalculation(result.calculation); setItems(result.calculation.items); setDeletedIds([]);
    return result;
  };
  const run = async (action: () => Promise<{ calculation: FulfillmentCalculation; message: string }>, title: string) => {
    setBusy(true);
    try {
      const result = await action();
      setCalculation(result.calculation); setItems(result.calculation.items); setRemark(result.calculation.remark || ""); setDeletedIds([]);
      setNotice({ title, message: result.message });
      return result;
    } catch (error) {
      setNotice({ title: "操作未完成", message: apiErrorMessage(error, title), error: true });
      return null;
    } finally { setBusy(false); }
  };

  if (loading) return <section className="calculation-workbench is-empty">正在读取算料数据...</section>;
  if (!bomPublished) return <section className="calculation-workbench is-empty"><div><Calculator size={18}/><strong>第2步：算料</strong><p>请先完成并发布上方BOM，发布后才能建立对应的算料版本。</p></div></section>;
  if (!calculation) return <section className="calculation-workbench is-empty"><div><Calculator size={18}/><strong>第2步：算料</strong><p>按当前BOM建立人工算料表；未来厂规自动计算会复用同一数据结构。</p><button disabled={busy} onClick={() => void run(() => initializeFulfillmentCalculation(doorId), "算料版本已建立")}>开始算料</button></div>{notice && <NoticeDialog title={notice.title} message={notice.message} onConfirm={() => setNotice(null)} />}</section>;

  return <section className="calculation-workbench">
    <header><div><span>第2步</span><h3>算料与下料单</h3><p>BOM V{calculation.bom_version} 对应算料 V{calculation.version}，同一BOM部件可拆成多条零件明细。</p></div><div><StatusChip tone={calculation.status === "已发布" ? "green" : calculation.status === "待确认" ? "amber" : "blue"}>{calculation.status}</StatusChip></div></header>
    <div className="calculation-actionbar">
      <input disabled={!editable} value={remark} onChange={(event) => setRemark(event.target.value)} placeholder="本次算料说明" />
      <button disabled={!editable || busy || !selectableComponents.length} onClick={() => setItems((current) => [...current, newItem(selectableComponents[0])])}><Plus size={14}/>新增零件</button>
      <button disabled={!editable || busy} onClick={() => void run(persist, "算料草稿已保存")}><Save size={14}/>保存算料</button>
      <button disabled={!editable || busy || !items.length} onClick={() => void run(async () => { await persist(); return submitFulfillmentCalculation(doorId); }, "算料已提交确认")}><CheckCheck size={14}/>提交确认</button>
      <button className="is-primary" disabled={busy || calculation.status !== "待确认"} onClick={() => void run(async () => { const result = await publishFulfillmentCalculation(doorId); await onPublished?.(); return result; }, "下料单已发布")}><Send size={14}/>发布下料单</button>
    </div>
    <div className="calculation-table-wrap"><table className="calculation-table"><thead><tr><th>BOM部件</th><th>零件名称</th><th>材质/规格</th><th>成品尺寸</th><th>下料长</th><th>下料宽</th><th>数量</th><th>单位</th><th>损耗%</th><th>实际用料</th><th>纹理方向</th><th>下料方式</th><th>备注</th><th>操作</th></tr></thead><tbody>{items.length ? items.map((item, index) => <tr key={item.id || index}>
      <td><select disabled={!editable} value={item.component_id} onChange={(event) => { const component = components.find((row) => row.id === Number(event.target.value)); updateItem(index, { component_id: Number(event.target.value), component_name: component?.name || "" }); }}>{components.map((component) => <option key={component.id} value={component.id}>{component.name}</option>)}</select></td>
      <td><input disabled={!editable} value={item.part_name} onChange={(event) => updateItem(index, { part_name: event.target.value })}/></td>
      <td><input disabled={!editable} value={item.material_specification} onChange={(event) => updateItem(index, { material_specification: event.target.value })}/></td>
      <td><input disabled={!editable} value={item.finished_size} onChange={(event) => updateItem(index, { finished_size: event.target.value })}/></td>
      {(["cut_length", "cut_width", "quantity"] as const).map((field) => <td key={field}><input disabled={!editable} type="number" min="0" step="0.1" value={item[field]} onChange={(event) => updateItem(index, { [field]: Number(event.target.value) })}/></td>)}
      <td><input disabled={!editable} value={item.unit} onChange={(event) => updateItem(index, { unit: event.target.value })}/></td>
      <td><input disabled={!editable} type="number" min="0" step="0.1" value={item.waste_rate} onChange={(event) => updateItem(index, { waste_rate: Number(event.target.value) })}/></td>
      <td><input disabled={!editable} type="number" min="0" step="0.001" value={item.actual_material_quantity} onChange={(event) => updateItem(index, { actual_material_quantity: Number(event.target.value) })}/></td>
      <td><input disabled={!editable} value={item.grain_direction} onChange={(event) => updateItem(index, { grain_direction: event.target.value })}/></td>
      <td><input disabled={!editable} value={item.cutting_method} onChange={(event) => updateItem(index, { cutting_method: event.target.value })}/></td>
      <td><input disabled={!editable} value={item.remark} onChange={(event) => updateItem(index, { remark: event.target.value })}/></td>
      <td><div className="calculation-row-actions"><button disabled={!editable} title="复制零件" onClick={() => { const component = components.find((row) => row.id === item.component_id); if (component) setItems((current) => [...current, newItem(component, item)]); }}><Copy size={14}/></button><button disabled={!editable} title="删除零件" className="is-danger" onClick={() => { if (item.id && item.id > 0) setDeletedIds((current) => [...current, item.id!]); setItems((current) => current.filter((_, itemIndex) => itemIndex !== index)); }}><Trash2 size={14}/></button></div></td>
    </tr>) : <tr><td colSpan={14} className="calculation-empty">当前BOM没有自动带入的自制部件，可从BOM补充自制部件后重新建立算料版本。</td></tr>}</tbody></table></div>
    <footer><span>来源为“手工”的明细可编辑；未来规则引擎生成的明细仍可在发布前修正。</span><strong>第3步：发布后冻结当前算料版本并形成下料单</strong></footer>
    {notice && <NoticeDialog title={notice.title} message={notice.message} onConfirm={() => setNotice(null)} />}
  </section>;
}
