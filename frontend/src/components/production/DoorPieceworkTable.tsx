"use client";

import { Check, Pencil, Plus, Save, Trash2 } from "lucide-react";
import { useState } from "react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import { savePieceworkAllocations } from "@/lib/operationsApi";
import type { DoorOperationFee, WorkforceEmployee } from "@/lib/operationsTypes";
import { formatPieceworkCents as money, parsePieceworkCents } from "@/lib/pieceworkMoney";

type Props = {
  fees: DoorOperationFee[];
  employees: WorkforceEmployee[];
  busy: boolean;
  notify: (message: string, error?: boolean) => void;
  onSaved: (fee: DoorOperationFee) => Promise<void>;
};

export default function DoorPieceworkTable({ fees, employees, busy, notify, onSaved }: Props) {
  const [selected, setSelected] = useState<DoorOperationFee | null>(null);
  if (!fees.length) return null;
  return <section className="door-piecework">
    <header><h3>整门计件</h3><span>{fees.length} 道工序 · 按樘</span></header>
    <div className="door-piecework__scroll"><table>
      <thead><tr>{["工序", "状态", "总额（元）", "已分（元）", "未分（元）", "操作"].map(label => <th key={label}>{label}</th>)}</tr></thead>
      <tbody>{fees.map(fee => <tr key={fee.id}>
        <td><strong>{fee.name}</strong><small>{fee.billing_operation_code}</small></td>
        <td><span className={`door-piecework__status ${fee.status === "已确认" ? "is-confirmed" : fee.status === "需核对" ? "is-warning" : ""}`}>{fee.status}</span>{fee.total_cents === 0 && fee.status !== "未设置计件单价" && <small>未设置计件单价</small>}</td>
        <td>{money(fee.total_cents)}</td><td>{money(fee.allocated_cents)}</td><td>{money(fee.remaining_cents)}</td>
        <td><button type="button" className="ui-button ui-button--secondary" disabled={busy || !["待分配", "已确认"].includes(fee.status)} title={fee.status === "已确认" ? "查看已确认分配" : fee.status === "待分配" ? "分配计件费用" : fee.status} onClick={() => setSelected(fee)}><Pencil size={14} />{fee.status === "已确认" ? "查看" : "分配"}</button></td>
      </tr>)}</tbody>
    </table></div>
    {selected && <AllocationDialog key={`${selected.id}-${selected.revision}`} fee={selected} employees={employees} notify={notify} onClose={() => setSelected(null)} onSaved={async fee => {
      setSelected(null);
      try { await onSaved(fee); }
      catch { notify("分配已保存，但页面刷新失败，请刷新查看", true); }
    }} />}
    <style jsx>{`
      .door-piecework{min-width:0;border:1px solid #e5e5ea;background:white}
      header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid #e5e5ea}
      h3{font-size:14px;font-weight:600}header span,small{font-size:11px;color:#636366}
      .door-piecework__scroll{overflow-x:auto}table{width:100%;min-width:660px;border-collapse:collapse;font-size:12px}
      th,td{padding:10px 14px;text-align:left;border-bottom:1px solid #ececef}th{font-weight:500;background:#f7f7f9;color:#636366}
      td:nth-child(n+3):nth-child(-n+5){font-variant-numeric:tabular-nums}small{display:block;margin-top:3px}
      .door-piecework__status{display:inline-block;padding:3px 7px;background:#f2f2f7;color:#636366;border-radius:4px}
      .is-confirmed{background:#eff9f0;color:#24713a}.is-warning{background:#fff2e8;color:#a65510}
    `}</style>
  </section>;
}

function AllocationDialog({ fee, employees, notify, onClose, onSaved }: Omit<Props, "fees" | "busy"> & { fee: DoorOperationFee; onClose: () => void }) {
  const [rows, setRows] = useState(fee.allocations.map(a => ({ employee_id: a.employee_id, amount: money(a.amount_cents), note: a.note })));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const readonly = fee.status === "已确认";
  const cents = rows.map(row => parsePieceworkCents(row.amount));
  const allocated = cents.reduce<number>((sum, value) => sum + (value ?? 0), 0);
  const remaining = fee.total_cents - allocated;
  const invalid = rows.some((row, i) => !row.employee_id || cents[i] === null)
    || new Set(rows.map(row => row.employee_id)).size !== rows.length || remaining < 0;
  const patch = (index: number, value: Partial<(typeof rows)[number]>) => setRows(current => current.map((row, i) => i === index ? { ...row, ...value } : row));
  const save = async (confirm: boolean) => {
    if (invalid || (confirm && !rows.length)) return;
    setSaving(true); setError("");
    try { const result = await savePieceworkAllocations(fee.id, { revision: fee.revision, confirm, allocations: rows }); notify(result.message); await onSaved(result.fee); }
    catch (err) { setError((err as { userMessage?: string; message?: string }).userMessage || (err as Error).message || "分配保存失败"); }
    finally { setSaving(false); }
  };
  return <ViewportDialog open title={`${fee.name} · ${readonly ? "已确认分配" : "计件分配"}`} size="medium" closeOnBackdrop={false} onClose={() => { if (!saving) onClose(); }} footer={!readonly ? <>
    <button type="button" className="ui-button ui-button--secondary" disabled={saving || invalid} onClick={() => void save(false)}><Save size={15} />保存草稿</button>
    <button type="button" className="ui-button ui-button--primary" disabled={saving || invalid || !rows.length} onClick={() => void save(true)}><Check size={15} />确认分配</button>
  </> : undefined}>
    <div className="fee-summary"><span>总额 <strong>{money(fee.total_cents)} 元</strong></span><span>已分 <strong>{money(allocated)} 元</strong></span><span className={remaining < 0 ? "is-error" : ""}>未分 <strong>{remaining < 0 ? "超额" : `${money(remaining)} 元`}</strong></span></div>
    <p className="fee-month">完工月份：{fee.completed_at?.slice(0, 7) || "-"}</p>
    {rows.map((row, index) => <div className="allocation-row" key={index}>
      <label>人员<select aria-label={`分配人员${index + 1}`} disabled={readonly || saving} value={row.employee_id || ""} onChange={e => patch(index, { employee_id: Number(e.target.value) })}>
        <option value="">选择人员</option>{employees.map(employee => <option key={employee.id} value={employee.id} disabled={rows.some((r, i) => i !== index && r.employee_id === employee.id)}>{employee.employee_no} · {employee.name}</option>)}
        {readonly && !employees.some(e => e.id === row.employee_id) && <option value={row.employee_id}>{fee.allocations[index]?.employee_no} · {fee.allocations[index]?.employee_name}</option>}
      </select></label>
      <label>金额（元）<input aria-label={`分配金额${index + 1}`} inputMode="decimal" value={row.amount} disabled={readonly || saving} onChange={e => patch(index, { amount: e.target.value })} /></label>
      <label>说明<input aria-label={`分配说明${index + 1}`} value={row.note} disabled={readonly || saving} onChange={e => patch(index, { note: e.target.value })} /></label>
      {!readonly && <button type="button" className="allocation-delete" title="删除分配人员" aria-label={`删除分配人员${index + 1}`} disabled={saving} onClick={() => setRows(rows.filter((_, i) => i !== index))}><Trash2 size={16} /></button>}
    </div>)}
    {!readonly && <button type="button" className="ui-button ui-button--secondary" disabled={saving || rows.length >= employees.length} onClick={() => setRows([...rows, { employee_id: 0, amount: "", note: "" }])}><Plus size={15} />添加人员</button>}
    <p className="fee-confirm-note">{readonly ? "已确认金额已冻结。" : `确认后分配不可直接修改。${remaining > 0 ? `未分的 ${money(remaining)} 元不计入工资。` : ""}`}</p>
    {invalid && <p role="alert" className="is-error">请选择不重复的人员，金额最多两位小数，合计不能超额。</p>}
    {error && <p role="alert" className="is-error">{error}</p>}
    <style jsx>{`
      .fee-summary{display:flex;flex-wrap:wrap;gap:10px 24px;border-bottom:1px solid #e5e5ea;padding-bottom:12px;font-size:13px}.fee-summary strong{font-variant-numeric:tabular-nums}
      .fee-month,.fee-confirm-note{color:#636366;font-size:12px;margin:12px 0}
      .allocation-row{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,.65fr) minmax(0,1fr) 32px;align-items:end;gap:8px;margin-bottom:12px}
      label{font-size:11px;color:#636366;min-width:0}input,select{display:block;width:100%;min-width:0;height:36px;border:1px solid #c7c7cc;background:white;padding:0 8px;margin-top:5px;color:#1c1c1e;font-size:12px;border-radius:4px}
      .allocation-delete{display:grid;place-items:center;height:36px;border:1px solid #e5e5ea;border-radius:4px;color:#b53333}.is-error{color:#b53333;font-size:12px;margin-top:10px}
      @media(max-width:560px){.allocation-row{grid-template-columns:minmax(0,1fr) minmax(0,.8fr) 32px}.allocation-row label:nth-child(3){grid-column:1/3;grid-row:2}.allocation-delete{grid-column:3;grid-row:1}}
    `}</style>
  </ViewportDialog>;
}
