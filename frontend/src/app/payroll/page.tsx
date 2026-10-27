"use client";

import { Calculator, CalendarDays, Check, Download, RefreshCw, Save, WalletCards } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import NoticeDialog from "@/components/door-cad/NoticeDialog";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import WorkspaceHeader from "@/components/workspace/WorkspaceHeader";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";
import { useAuth } from "@/hooks/useAuth";
import { hasBusinessPermission } from "@/lib/managementAccess";
import { calculatePayroll, getAttendance, getEmployees, getPayrollPeriod, getPayrollPeriods, saveAttendance, updatePayrollEntry, updatePayrollStatus } from "@/lib/operationsApi";
import type { AttendanceRow, PayrollEntry, PayrollPeriod, WorkforceEmployee } from "@/lib/operationsTypes";

const monthNow = () => new Date().toISOString().slice(0, 7);
type AttendanceForm = { employee_id: number; work_date: string; regular_hours: number; overtime_hours: number; leave_hours: number; remark: string };

export default function PayrollPage() {
  const { user } = useAuth();
  const canRead = hasBusinessPermission(user, "payroll.read");
  const canWrite = hasBusinessPermission(user, "payroll.write");
  const canApprove = hasBusinessPermission(user, "payroll.approve");
  const canUnlock = hasBusinessPermission(user, "payroll.unlock");
  const canAttend = hasBusinessPermission(user, "attendance.write");
  const [tab, setTab] = useState<"payroll" | "attendance">("payroll");
  const [month, setMonth] = useState(monthNow());
  const [periods, setPeriods] = useState<PayrollPeriod[]>([]);
  const [period, setPeriod] = useState<PayrollPeriod | null>(null);
  const [employees, setEmployees] = useState<WorkforceEmployee[]>([]);
  const [attendance, setAttendance] = useState<AttendanceRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ title: string; message: string } | null>(null);
  const [transition, setTransition] = useState<{ periodId: number; from: PayrollPeriod["status"]; to: PayrollPeriod["status"] } | null>(null);
  const [reason, setReason] = useState("");
  const [attendanceForm, setAttendanceForm] = useState<AttendanceForm>({ employee_id: 0, work_date: new Date().toISOString().slice(0, 10), regular_hours: 8, overtime_hours: 0, leave_hours: 0, remark: "" });
  const activeTab = canRead ? tab : "attendance";
  const load = useCallback(async () => {
    if (!canRead && !canAttend) return;
    const [p, e, a] = await Promise.all([canRead ? getPayrollPeriods() : Promise.resolve([]), getEmployees(), getAttendance(month)]);
    setPeriods(p); setEmployees(e.filter(x => x.is_active)); setAttendance(a);
  }, [month, canRead, canAttend]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load().catch(error => setNotice({ title: "加载失败", message: msg(error, "工资数据加载失败") })), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  const total = useMemo(() => period?.entries?.reduce((sum, row) => sum + Number(row.payable_amount || 0), 0) || 0, [period]);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try { await action(); } catch (error) { setNotice({ title: "操作失败", message: msg(error, "操作失败，请刷新后重试") }); }
    finally { setBusy(false); }
  };
  const calculate = () => run(async () => {
    const result = await calculatePayroll(month);
    setPeriod(result.period); setNotice({ title: "计算完成", message: result.message }); await load();
  });
  const saveEntry = (row: PayrollEntry) => run(async () => {
    const result = await updatePayrollEntry(row.id, row);
    setPeriod(result.period); setNotice({ title: "保存成功", message: result.message });
  });
  const startTransition = (to: PayrollPeriod["status"]) => {
    if (!period) return;
    setReason(""); setTransition({ periodId: period.id, from: period.status, to });
  };
  const transit = () => run(async () => {
    if (!transition) return;
    const result = await updatePayrollStatus(transition.periodId, transition.to, reason, transition.from);
    setPeriod(result.period); setTransition(null); setNotice({ title: "状态已更新", message: result.message }); await load();
  });
  const exportCsv = () => {
    if (!period?.entries?.length) return;
    const header = ["员工编号", "姓名", "班组", "基本工资", "计件", "加班", "补贴", "奖金", "扣款", "社保", "个税", "其他代扣", "应发", "备注"];
    const rows = period.entries.map(r => [r.employee_no, r.name, r.team, r.base_salary, r.piecework_amount, r.overtime_amount, r.allowance, r.bonus, r.deduction, r.social_insurance, r.tax, r.other_withholding, r.payable_amount, r.remark]);
    const csv = "\ufeff" + [header, ...rows].map(row => row.map(v => `"${String(v ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = `工资表_${period.month}.csv`; a.click(); URL.revokeObjectURL(a.href);
  };
  return <div className="min-h-screen bg-[#F2F2F7]"><main className="workspace-page workspace-page--wide space-y-4">
    <WorkspaceHeader title="工资管理" context={<><WalletCards size={14}/>经营管理 / 人员工资</>} actions={<button className="ui-button ui-button--secondary" disabled={busy} onClick={() => void run(load)}><RefreshCw size={15}/>刷新</button>}/>
    <div className="flex flex-wrap items-center gap-3">
      {canRead && <WorkspaceTabs items={[{ key: "payroll", label: "月度工资" }, { key: "attendance", label: "考勤登记" }] as const} value={tab} onChange={setTab} ariaLabel="工资管理视图"/>}
      <label className="ml-auto flex items-center gap-2 text-sm"><CalendarDays size={15}/><input type="month" value={month} disabled={busy} onChange={e => { setMonth(e.target.value); setPeriod(null); }} className="h-9 border border-[#C7C7CC] bg-white px-3"/></label>
    </div>
    {activeTab === "attendance" ? <AttendancePanel rows={attendance} employees={employees} form={attendanceForm} setForm={setAttendanceForm} disabled={busy || !canAttend} submit={() => run(async () => {
      if (!attendanceForm.employee_id) { setNotice({ title: "无法保存", message: "请选择员工" }); return; }
      const result = await saveAttendance(attendanceForm); setNotice({ title: "保存成功", message: result.message }); await load();
    })}/> : <section className="workspace-panel overflow-hidden">
      <header className="workspace-panel__header"><div><h2>{month} 工资表</h2><p>{period ? `${period.status} · ${period.entries?.length || 0} 人 · 合计 ¥${total.toFixed(2)}` : "选择工资期间"}</p></div>
        <div className="flex flex-wrap gap-2">
          <select aria-label="工资期间" value={period?.id || ""} disabled={busy} onChange={e => { const found = periods.find(p => p.id === Number(e.target.value)); if (found) void run(async () => { const detail = await getPayrollPeriod(found.id); setMonth(found.month); setPeriod(detail); }); }} className="h-9 border border-[#C7C7CC] bg-white px-3 text-sm"><option value="">历史月份</option>{periods.map(p => <option key={p.id} value={p.id}>{p.month} · {p.status}</option>)}</select>
          {canWrite && <button className="ui-button ui-button--primary" disabled={busy || (period ? period.status !== "草稿" : periods.some(p => p.month === month && p.status !== "草稿"))} onClick={() => void calculate()}><Calculator size={15}/>汇总计算</button>}
          <button className="ui-button ui-button--secondary" disabled={!period || busy} onClick={exportCsv}><Download size={15}/>导出 CSV</button>
          {period?.status === "草稿" && canWrite && <button className="ui-button ui-button--secondary" disabled={busy} onClick={() => startTransition("待审核")}><Check size={15}/>提交审核</button>}
          {period?.status === "待审核" && canApprove && <><button className="ui-button ui-button--primary" disabled={busy} onClick={() => startTransition("已审批")}><Check size={15}/>审批通过</button><button className="ui-button ui-button--secondary" disabled={busy} onClick={() => startTransition("草稿")}>退回草稿</button></>}
          {period?.status === "已审批" && canApprove && <button className="ui-button ui-button--secondary" disabled={busy} onClick={() => startTransition("已锁定")}>锁定工资</button>}
          {period && ["已审批", "已锁定"].includes(period.status) && canUnlock && <button className="ui-button ui-button--secondary" disabled={busy} onClick={() => startTransition("草稿")}>{period.status === "已锁定" ? "解锁为草稿" : "撤销审批"}</button>}
        </div>
      </header>
      <PayrollTable period={period} setPeriod={setPeriod} save={saveEntry} disabled={busy || !canWrite || period?.status !== "草稿"}/>
      {period && <details className="border-t border-[#E5E5EA] p-4"><summary className="cursor-pointer text-sm font-semibold">操作记录（{period.audit_events?.length || 0}）</summary><div className="mt-3 divide-y divide-[#E5E5EA]">{period.audit_events?.map(event => <div key={event.id} className="space-y-1 py-3 text-xs text-[#636366]"><p>{event.created_at} · {event.operator_name || event.operator_uid}（{event.operator_uid}）· {event.action}</p><p className="break-words whitespace-pre-wrap">{auditText(event.detail)}</p></div>)}</div></details>}
    </section>}
  </main>
    <ViewportDialog open={Boolean(transition)} title={transition?.to === "草稿" ? "退回工资草稿" : `确认${transition?.to || ""}`} size="small" onClose={() => { if (!busy) setTransition(null); }} footer={<><button className="ui-button ui-button--secondary" disabled={busy} onClick={() => setTransition(null)}>取消</button><button className="ui-button ui-button--primary" disabled={busy || (transition?.to === "草稿" && !reason.trim())} onClick={() => void transit()}><Check size={15}/>确认</button></>}>
      <p className="mb-4 text-sm">{month} · {transition?.from} → {transition?.to}</p>
      <label className="block text-sm">操作原因{transition?.to === "草稿" ? "（必填）" : "（选填）"}<textarea aria-label="工资操作原因" value={reason} maxLength={1000} onChange={e => setReason(e.target.value)} className="mt-2 min-h-24 w-full border border-[#C7C7CC] p-2"/></label>
    </ViewportDialog>
    {notice && <NoticeDialog title={notice.title} message={notice.message} onConfirm={() => setNotice(null)}/>}
  </div>;
}

function PayrollTable({ period, setPeriod, save, disabled }: { period: PayrollPeriod | null; setPeriod: (p: PayrollPeriod) => void; save: (r: PayrollEntry) => Promise<void>; disabled: boolean }) {
  if (!period) return <div className="p-12 text-center text-sm text-[#8E8E93]">暂无工资表</div>;
  const change = (id: number, key: keyof PayrollEntry, value: string | number) => setPeriod({ ...period, entries: period.entries?.map(r => r.id === id ? { ...r, [key]: value } : r) });
  return <div className="overflow-x-auto"><table className="payroll-table w-full min-w-[1650px] text-sm"><thead><tr>{["员工", "基本工资", "计件工资", "加班金额", "补贴", "奖金", "扣款", "社保", "个税", "其他代扣", "应发工资", "备注", "操作"].map(v => <th key={v}>{v}</th>)}</tr></thead>
    <tbody>{period.entries?.map(row => <tr key={row.id}><td><strong>{row.employee_no}</strong><small>{row.name} · {row.team || "未分组"}</small></td><Money value={row.base_salary} disabled/><Money value={row.piecework_amount} disabled/>
      {(["overtime_amount", "allowance", "bonus", "deduction", "social_insurance", "tax", "other_withholding"] as const).map(key => <Money key={key} value={row[key]} disabled={disabled} onChange={v => change(row.id, key, v)}/>)}
      <td className="font-semibold">¥{Number(row.payable_amount).toFixed(2)}</td><td><input aria-label={`${row.name}工资备注`} disabled={disabled} value={row.remark || ""} onChange={e => change(row.id, "remark", e.target.value)}/></td><td><button className="ui-button ui-button--secondary" disabled={disabled} onClick={() => void save(row)}><Save size={14}/>保存</button></td></tr>)}</tbody></table>
    <style jsx global>{`.payroll-table th,.payroll-table td{border-bottom:1px solid #e5e5ea;padding:.65rem;text-align:left;white-space:nowrap}.payroll-table th{background:#f7f7f9;color:#636366;font-size:.75rem;font-weight:500}.payroll-table td:first-child{min-width:130px}.payroll-table td small{display:block;color:#636366;margin-top:.2rem}.payroll-table td input{height:2.25rem;width:100px;border:1px solid #c7c7cc;padding:0 .5rem}.payroll-table td input:disabled{border-color:transparent;background:transparent}`}</style>
  </div>;
}
function Money({ value, disabled, onChange }: { value: number; disabled?: boolean; onChange?: (v: number) => void }) {
  return <td><input type="number" disabled={disabled} value={value || ""} onChange={e => onChange?.(Number(e.target.value) || 0)}/></td>;
}
function AttendancePanel({ rows, employees, form, setForm, disabled, submit }: { rows: AttendanceRow[]; employees: WorkforceEmployee[]; form: AttendanceForm; setForm: (v: AttendanceForm) => void; disabled: boolean; submit: () => Promise<void> }) {
  return <section className="workspace-panel overflow-hidden"><header className="workspace-panel__header"><h2>每日考勤</h2></header>
    <fieldset disabled={disabled} className="grid gap-3 border-b bg-[#FAFAFB] p-4 md:grid-cols-3 xl:grid-cols-6">
      <select aria-label="考勤员工" value={form.employee_id || ""} onChange={e => setForm({ ...form, employee_id: Number(e.target.value) })}><option value="">选择员工</option>{employees.map(e => <option key={e.id} value={e.id}>{e.employee_no} · {e.name}</option>)}</select>
      <input aria-label="考勤日期" type="date" value={form.work_date} onChange={e => setForm({ ...form, work_date: e.target.value })}/><input aria-label="正常工时" type="number" value={form.regular_hours} onChange={e => setForm({ ...form, regular_hours: Number(e.target.value) || 0 })}/><input aria-label="加班工时" type="number" value={form.overtime_hours} onChange={e => setForm({ ...form, overtime_hours: Number(e.target.value) || 0 })}/><input aria-label="考勤备注" value={form.remark} onChange={e => setForm({ ...form, remark: e.target.value })}/><button className="ui-button ui-button--primary" onClick={() => void submit()}><Save size={15}/>保存考勤</button>
    </fieldset>
    <div className="divide-y">{rows.length ? rows.map(r => <div key={r.id} className="grid gap-2 p-3 text-sm md:grid-cols-6"><strong>{r.employee_no} · {r.name}</strong><span>{r.work_date}</span><span>正常 {r.regular_hours}h</span><span>加班 {r.overtime_hours}h</span><span>请假 {r.leave_hours}h</span><span>{r.remark || "-"}</span></div>) : <div className="p-10 text-center text-sm text-[#8E8E93]">本月暂无考勤</div>}</div>
    <style jsx>{`input,select{height:2.5rem;width:100%;border:1px solid #c7c7cc;background:#fff;padding:0 .75rem;font-size:.875rem}`}</style>
  </section>;
}
function msg(error: unknown, fallback: string) {
  return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback;
}
function auditText(detail: string) {
  try {
    const item = JSON.parse(detail);
    if (item.from) return `${item.from} → ${item.to}${item.reason ? ` · ${item.reason}` : ""}`;
    if (item.before) return `明细 #${item.entry_id}：${JSON.stringify(item.before)} → ${JSON.stringify(item.after)}`;
    if (item.month) return `${item.month} · ${item.employee_count} 人`;
  } catch { /* Historical audit entries may contain plain text. */ }
  return detail;
}
