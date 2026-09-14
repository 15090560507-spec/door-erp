"use client";

import { Plus, Save, UserRoundX } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { createEmployee, deactivateEmployee, getEmployees, updateEmployee, type EmployeePayload } from "@/lib/operationsApi";
import type { WorkforceEmployee } from "@/lib/operationsTypes";

const emptyEmployee = (): EmployeePayload => ({ employee_no: "", name: "", team: "", role_name: "", capabilities: [], work_center: "", wage_type: "月薪+计件", base_salary: 0, hire_date: "", leave_date: "", is_active: true, remark: "" });

export default function EmployeeCatalog({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [rows, setRows] = useState<WorkforceEmployee[]>([]);
  const [draft, setDraft] = useState<EmployeePayload>(emptyEmployee());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => setRows(await getEmployees()), []);
  useEffect(() => { void load().catch((error) => notify(message(error, "员工档案加载失败"), true)); }, [load, notify]);
  const edit = (row: WorkforceEmployee) => { setEditingId(row.id); setDraft({ ...row, capabilities: [...row.capabilities] }); };
  const save = async () => {
    if (!draft.employee_no.trim() || !draft.name.trim()) return notify("员工编号和姓名为必填项", true);
    setBusy(true);
    try {
      const result = editingId ? await updateEmployee(editingId, draft) : await createEmployee(draft);
      notify(result.message); setDraft(emptyEmployee()); setEditingId(null); await load();
    } catch (error) { notify(message(error, "员工档案保存失败"), true); } finally { setBusy(false); }
  };
  return <section className="workspace-panel overflow-hidden">
    <header className="workspace-panel__header"><div><h2>人员档案</h2><p>生产执行、拼装分配、考勤和计件工资共用同一员工编号。</p></div><button className="ui-button ui-button--secondary" onClick={() => { setEditingId(null); setDraft(emptyEmployee()); }}><Plus size={15}/>新增员工</button></header>
    <div className="grid gap-3 border-b border-[#E5E5EA] bg-[#FAFAFB] p-4 md:grid-cols-3 xl:grid-cols-6">
      <Field label="员工编号 *"><input value={draft.employee_no} onChange={(e)=>setDraft({...draft,employee_no:e.target.value})}/></Field>
      <Field label="姓名 *"><input value={draft.name} onChange={(e)=>setDraft({...draft,name:e.target.value})}/></Field>
      <Field label="班组"><input value={draft.team} onChange={(e)=>setDraft({...draft,team:e.target.value})}/></Field>
      <Field label="岗位"><input value={draft.role_name} onChange={(e)=>setDraft({...draft,role_name:e.target.value})}/></Field>
      <Field label="工作中心"><input value={draft.work_center} onChange={(e)=>setDraft({...draft,work_center:e.target.value})}/></Field>
      <Field label="工资模式"><select value={draft.wage_type} onChange={(e)=>setDraft({...draft,wage_type:e.target.value})}><option>月薪+计件</option><option>月薪</option><option>计件</option></select></Field>
      <Field label="基本工资"><input type="number" min="0" value={draft.base_salary||""} onChange={(e)=>setDraft({...draft,base_salary:Number(e.target.value)||0})}/></Field>
      <Field label="入职日期"><input type="date" value={draft.hire_date} onChange={(e)=>setDraft({...draft,hire_date:e.target.value})}/></Field>
      <Field label="能力标签"><input value={draft.capabilities.join("、")} onChange={(e)=>setDraft({...draft,capabilities:e.target.value.split(/[、,，]/).map(v=>v.trim()).filter(Boolean)})} placeholder="下料、折弯、拼装"/></Field>
      <Field label="备注"><input value={draft.remark} onChange={(e)=>setDraft({...draft,remark:e.target.value})}/></Field>
      <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={draft.is_active} onChange={(e)=>setDraft({...draft,is_active:e.target.checked})}/>在职启用</label>
      <div className="flex items-end"><button disabled={busy} className="ui-button ui-button--primary w-full" onClick={()=>void save()}><Save size={15}/>{editingId ? "保存修改" : "建立档案"}</button></div>
    </div>
    <div className="overflow-x-auto"><table className="w-full min-w-[980px] text-sm"><thead><tr>{["员工","班组/岗位","工作中心","工资模式","基本工资","能力","状态","操作"].map(v=><th key={v}>{v}</th>)}</tr></thead><tbody>{rows.map(row=><tr key={row.id}><td><strong>{row.employee_no}</strong><small>{row.name}</small></td><td>{row.team||"-"}<small>{row.role_name||"-"}</small></td><td>{row.work_center||"-"}</td><td>{row.wage_type}</td><td>¥{Number(row.base_salary||0).toFixed(2)}</td><td>{row.capabilities.join("、")||"-"}</td><td><span className={row.is_active?"text-[#248A3D]":"text-[#8E8E93]"}>{row.is_active?"在职":"已停用"}</span></td><td><div className="flex gap-2"><button onClick={()=>edit(row)}>编辑</button>{row.is_active&&<button title="停用并保留历史" onClick={async()=>{setBusy(true);try{const r=await deactivateEmployee(row.id);notify(r.message);await load();}catch(error){notify(message(error,"停用失败"),true);}finally{setBusy(false);}}}><UserRoundX size={15}/></button>}</div></td></tr>)}</tbody></table></div>
    <style jsx>{`input,select{height:2.5rem;width:100%;border:1px solid #c7c7cc;background:#fff;padding:0 .75rem;font-size:.875rem}th,td{border-bottom:1px solid #e5e5ea;padding:.75rem;text-align:left}th{background:#f7f7f9;color:#636366;font-size:.75rem;font-weight:500}td small{display:block;margin-top:.2rem;color:#636366}`}</style>
  </section>;
}

function Field({label,children}:{label:string;children:React.ReactNode}){return <label className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span>{children}</label>}
function message(error:unknown,fallback:string){return (error as {userMessage?:string;message?:string})?.userMessage||(error as {message?:string})?.message||fallback}
