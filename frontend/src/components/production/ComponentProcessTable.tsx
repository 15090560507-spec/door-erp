"use client";

import { ChevronRight, PackageCheck } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import type { DoorUnitDetail, FulfillmentComponent, FulfillmentWorkPackage } from "@/lib/fulfillmentTypes";

type WorkPayload = { status: string; executor_uid: string; actual_quantity?: number; remark: string };

type Props = {
  door: DoorUnitDetail;
  busy: boolean;
  selectedIds: number[];
  onToggle: (workId: number, checked: boolean) => void;
  onSave: (work: FulfillmentWorkPackage, payload: WorkPayload) => Promise<void>;
  onInbound: (componentId: number, quantity: number) => Promise<void>;
  onIssueAll: () => Promise<void>;
};

const terminalStatuses = new Set(["已完成", "已取消"]);

function amount(value: number | undefined) {
  return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 3 });
}

function isSelfMade(component: FulfillmentComponent) {
  return component.procurement_mode === "make" || ["assembly", "manufactured_part"].includes(component.item_kind || "");
}

function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "blue" | "green" | "amber" | "red" }) {
  return <span className={`component-process-pill is-${tone}`}>{children}</span>;
}

export default function ComponentProcessTable({ door, busy, selectedIds, onToggle, onSave, onInbound, onIssueAll }: Props) {
  const components = door.technical_package?.components || [];
  const works = door.technical_package?.work_packages || [];
  const worksByComponent = useMemo(() => {
    const result = new Map<number, FulfillmentWorkPackage[]>();
    works.forEach((work) => {
      if (!work.component_id) return;
      result.set(work.component_id, [...(result.get(work.component_id) || []), work]);
    });
    result.forEach((rows) => rows.sort((left, right) => Number(left.id || 0) - Number(right.id || 0)));
    return result;
  }, [works]);
  const materialByComponent = useMemo(() => new Map(
    (door.material_requirement?.items || []).filter((item) => item.component_id).map((item) => [item.component_id!, item]),
  ), [door.material_requirement?.items]);
  const inventoryByComponent = useMemo(() => new Map(
    (door.component_inventory || []).map((item) => [item.component_id, item]),
  ), [door.component_inventory]);
  const inboundRows = door.component_inventory || [];
  const remaining = inboundRows.filter((item) => item.remaining_inbound_quantity > 0.005).length;
  const available = inboundRows.filter((item) => item.available_quantity > 0.005).length;

  return <section className="component-process-board">
    <header className="component-process-board__header">
      <div><h3>部件生产进度</h3><p>逐项对应当前 BOM；自制件展开加工工序，外购件显示库存与采购状态。</p></div>
      <div><span>{components.length} 项 BOM</span><span>{works.filter((item) => terminalStatuses.has(item.status || "")).length}/{works.length} 道工序完成</span><button type="button" disabled={busy || remaining > 0 || available === 0} onClick={() => void onIssueAll()}><PackageCheck size={14} />拼装领用全部</button></div>
    </header>
    <div className="component-process-table-wrap">
      <table className="component-process-table">
        <thead><tr><th className="is-check"></th><th>部件 / 工序</th><th>规格与计划量</th><th>材料状态</th><th>执行人员</th><th>当前状态</th><th>数量进度</th><th>操作</th></tr></thead>
        <tbody>{components.length ? components.flatMap((component) => {
          const componentId = component.id || 0;
          const componentWorks = worksByComponent.get(componentId) || [];
          const material = materialByComponent.get(componentId);
          const inventory = inventoryByComponent.get(componentId);
          const selfMade = isSelfMade(component);
          const assembly = component.item_kind === "assembly";
          const activeWorks = componentWorks.filter((item) => item.id && !terminalStatuses.has(item.status || ""));
          const materialState = selfMade
            ? "按图自制"
            : !material ? component.acquisition_method || "待确定"
              : material.shortage_quantity > 0.005 ? `缺 ${amount(material.shortage_quantity)} ${material.unit}`
                : material.issued_quantity >= material.required_quantity - 0.005 ? "已领料"
                  : material.received_quantity > 0 ? "已到货"
                    : material.purchased_quantity > 0 ? "采购中"
                      : material.reserved_quantity >= material.required_quantity - 0.005 ? "库存已预留" : "待备料";
          const allDone = componentWorks.length > 0 && componentWorks.every((item) => terminalStatuses.has(item.status || ""));
          const overallState = !selfMade ? materialState : !componentWorks.length ? "未生成工序" : allDone ? (assembly ? "拼装完成" : "加工完成") : componentWorks.some((item) => item.status === "进行中") ? "加工中" : "待加工";
          const planned = inventory?.planned_quantity || component.quantity || 0;
          const parent = <tr className="component-process-parent" key={`component-${componentId}`}>
            <td className="is-check"><input type="checkbox" aria-label={`选择${component.name}未完成工序`} disabled={!activeWorks.length} checked={activeWorks.length > 0 && activeWorks.every((item) => selectedIds.includes(item.id!))} onChange={(event) => activeWorks.forEach((item) => onToggle(item.id!, event.target.checked))} /></td>
            <td><strong>{component.name}</strong><small>{assembly ? "装配总成" : selfMade ? "自制部件" : "材料/配件"}</small></td>
            <td><span>{component.specification || component.operation_code || "未填写规格"}</span><small>{amount(planned)} {inventory?.unit || component.unit}</small></td>
            <td><Pill tone={materialState.startsWith("缺") ? "red" : selfMade ? "blue" : ["已领料", "已到货", "库存已预留"].includes(materialState) ? "green" : "amber"}>{materialState}</Pill></td>
            <td><span className="component-process-muted">{componentWorks.find((item) => item.executor_uid)?.executor_uid || "按工序分配"}</span></td>
            <td><Pill tone={allDone ? "green" : overallState === "未生成工序" ? "red" : "blue"}>{overallState}</Pill></td>
            <td>{inventory ? `${amount(inventory.inbound_quantity)} / ${amount(inventory.planned_quantity)} ${inventory.unit}` : `${componentWorks.filter((item) => terminalStatuses.has(item.status || "")).length} / ${componentWorks.length} 道`}</td>
            <td>{inventory ? <button type="button" disabled={busy || inventory.remaining_inbound_quantity <= 0.005} onClick={() => void onInbound(componentId, inventory.remaining_inbound_quantity)}>完工入半成品</button> : <span className="component-process-muted">{selfMade ? "按工序推进" : "由库存/采购处理"}</span>}</td>
          </tr>;
          const children = componentWorks.length
            ? componentWorks.map((work) => <ProcessRow key={work.id || `${componentId}-${work.name}`} work={work} busy={busy} selected={Boolean(work.id && selectedIds.includes(work.id))} onToggle={onToggle} onSave={onSave} />)
            : [<tr className="component-process-empty" key={`empty-${componentId}`}><td></td><td colSpan={7}><ChevronRight size={13} />{selfMade ? "未生成工序，请重新发布当前 BOM 或建立新版本" : `无需制造工序，当前状态：${materialState}`}</td></tr>];
          return [parent, ...children];
        }) : <tr className="component-process-empty"><td colSpan={8}>BOM 发布后显示部件生产进度</td></tr>}</tbody>
      </table>
    </div>
  </section>;
}

function ProcessRow({ work, busy, selected, onToggle, onSave }: { work: FulfillmentWorkPackage; busy: boolean; selected: boolean; onToggle: (workId: number, checked: boolean) => void; onSave: Props["onSave"] }) {
  const [executor, setExecutor] = useState(work.executor_uid || "");
  const [status, setStatus] = useState(work.status || "待排单");
  const [remark, setRemark] = useState(work.remark || "");
  const terminal = terminalStatuses.has(work.status || "");
  return <tr className={`component-process-child${selected ? " is-selected" : ""}`}>
    <td className="is-check"><input type="checkbox" disabled={terminal || !work.id} checked={selected} onChange={(event) => work.id && onToggle(work.id, event.target.checked)} /></td>
    <td><strong><ChevronRight size={13} />{work.name.split("·").pop()}</strong><small>{work.route || work.category}</small></td>
    <td><span>{work.operation_code || "工序"}</span><small>{work.inspection_required ? "需要过程检验" : "常规工序"}</small></td>
    <td><Pill tone={work.material_ready ? "green" : "amber"}>{work.material_ready ? "材料可用" : work.blocked_reason || work.readiness_status || "待物料"}</Pill></td>
    <td><input list="workforce-employees" value={executor} onChange={(event) => setExecutor(event.target.value)} placeholder="未分配" /></td>
    <td><select disabled={terminal} value={status} onChange={(event) => setStatus(event.target.value)}>{["待排单", "已排单", "进行中", "待质检", "已完成", "暂停", "异常", "返工", "已取消"].map((value) => <option key={value}>{value}</option>)}</select></td>
    <td>{amount(work.actual_quantity)} / {amount(work.quantity)} {work.unit}</td>
    <td><div className="component-process-actions"><input value={remark} onChange={(event) => setRemark(event.target.value)} placeholder="说明" /><button type="button" disabled={busy || terminal} onClick={() => void onSave(work, { status, executor_uid: executor, actual_quantity: status === "已完成" ? work.quantity : work.actual_quantity, remark })}>保存</button></div></td>
  </tr>;
}
