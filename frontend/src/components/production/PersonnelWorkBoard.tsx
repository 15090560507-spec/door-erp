"use client";

import { ChevronRight, RefreshCw, UsersRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getPersonnelWork } from "@/lib/operationsApi";
import type { PersonnelWorkDepartment } from "@/lib/operationsTypes";

type Props = {
  onOpenWork: (orderId: number, doorUnitId: number) => Promise<void>;
  notify: (message: string, error?: boolean) => void;
};

function errorMessage(error: unknown) {
  return (error as { userMessage?: string; message?: string })?.userMessage
    || (error as { message?: string })?.message
    || "人员工作加载失败";
}

export default function PersonnelWorkBoard({ onOpenWork, notify }: Props) {
  const [departments, setDepartments] = useState<PersonnelWorkDepartment[]>([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try { setDepartments(await getPersonnelWork()); }
    catch (error) { notify(errorMessage(error), true); }
    finally { setLoading(false); }
  }, [notify]);
  useEffect(() => { void load(); }, [load]);
  const summary = useMemo(() => {
    const employees = departments.flatMap((item) => item.employees);
    return { total: employees.length, working: employees.filter((item) => item.current_work).length };
  }, [departments]);

  return <section className="personnel-work-board">
    <header className="personnel-work-board__header">
      <div><h2><UsersRound size={17} />人员工作</h2><p>按部门查看人员当前正在处理的一项工作。</p></div>
      <div><span>{summary.working} 人工作中</span><span>{summary.total - summary.working} 人空闲</span><button type="button" disabled={loading} onClick={() => void load()} title="刷新人员工作"><RefreshCw size={15} className={loading ? "animate-spin" : ""} /></button></div>
    </header>
    {loading && !departments.length ? <div className="personnel-work-board__empty">正在加载人员工作...</div> : departments.length === 0 ? <div className="personnel-work-board__empty">暂无在职人员，请先在基础资料中建立人员档案</div> : <div className="personnel-work-board__departments">
      {departments.map((department) => {
        const working = department.employees.filter((item) => item.current_work).length;
        return <details key={department.name} open className="personnel-department">
          <summary><span>{department.name}</span><small>{department.employees.length} 人 · {working} 人工作中</small></summary>
          <div className="personnel-department__table">
            <div className="personnel-department__head"><span>人员</span><span>当前工作</span><span>状态</span><span></span></div>
            {department.employees.map((employee) => <div key={employee.id} className="personnel-work-row">
              <div><strong>{employee.name}</strong><small>{employee.employee_no}{employee.role_name ? ` · ${employee.role_name}` : ""}</small></div>
              <div>{employee.current_work ? <button type="button" onClick={() => void onOpenWork(employee.current_work!.order_id, employee.current_work!.door_unit_id)}><strong>{employee.current_work.production_no}</strong><small>{employee.current_work.operation_name}</small></button> : <span className="personnel-work-row__empty">暂无分配</span>}</div>
              <div><span className={`personnel-work-status is-${employee.current_work ? "working" : "idle"}`}>{employee.status}</span>{employee.current_work && <small>{employee.current_work.status}</small>}</div>
              <div>{employee.current_work && <button type="button" className="personnel-work-row__open" title="打开对应门樘" onClick={() => void onOpenWork(employee.current_work!.order_id, employee.current_work!.door_unit_id)}><ChevronRight size={17} /></button>}</div>
            </div>)}
          </div>
        </details>;
      })}
    </div>}
  </section>;
}
