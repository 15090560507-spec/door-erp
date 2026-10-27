"use client";

import { RefreshCw, Save, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { api, apiErrorMessage } from "@/lib/api";
import { isBusinessAdmin } from "@/lib/managementAccess";
import type { UserInfo } from "@/lib/types";

type Account = UserInfo & { management_permissions?: string[] };
type Permission = { key: string; label: string };
type Audit = { operator_uid: string; before: string[]; after: string[]; reason: string; created_at: string };

export default function BusinessPermissionsPanel() {
  const { user } = useAuth();
  const allowed = isBusinessAdmin(user);
  const [catalog, setCatalog] = useState<Permission[]>([]);
  const [users, setUsers] = useState<Record<string, Account>>({});
  const [uid, setUid] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [events, setEvents] = useState<Audit[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const account = users[uid];
  const fixed = isBusinessAdmin(account);
  const load = useCallback(async () => {
    if (!allowed) return;
    const { data } = await api.get<{ catalog: Permission[]; users: Record<string, Account> }>("/business-access");
    setCatalog(data.catalog);
    setUsers(data.users);
  }, [allowed]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load().catch(error => setMessage(apiErrorMessage(error, "经营权限加载失败"))), 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  useEffect(() => {
    let cancelled = false;
    if (uid) void api.get<{ events: Audit[] }>(`/business-access/${encodeURIComponent(uid)}/history`)
      .then(({ data }) => { if (!cancelled) setEvents(data.events); })
      .catch(error => { if (!cancelled) setMessage(apiErrorMessage(error, "授权记录加载失败")); });
    return () => { cancelled = true; };
  }, [uid, account]);
  const save = async () => {
    if (!uid || fixed || !reason.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.put<{ users: Record<string, Account>; message: string }>(`/business-access/${encodeURIComponent(uid)}`, { permissions: selected, reason });
      setUsers(data.users);
      setSelected(data.users[uid]?.management_permissions || data.users[uid]?.permissions || []);
      setReason("");
      setMessage(data.message);
    } catch (error) { setMessage(apiErrorMessage(error, "权限保存失败")); }
    finally { setBusy(false); }
  };
  if (!allowed) return null;
  return <details className="mb-6 overflow-hidden rounded-lg border border-[#D1D1D6] bg-white">
    <summary className="cursor-pointer px-5 py-4 font-semibold"><ShieldCheck size={17} className="mr-2 inline"/>经营权限管理</summary>
    <div className="space-y-4 border-t border-[#E5E5EA] p-5">
      <div className="flex flex-wrap gap-2">
        <select aria-label="权限账号" className="h-10 min-w-0 flex-1 border border-[#C7C7CC] px-3 text-sm" value={uid} disabled={busy} onChange={e => { setUid(e.target.value); const target = users[e.target.value]; setSelected(target?.management_permissions || target?.permissions || []); setReason(""); setEvents([]); }}>
          <option value="">选择账号</option>{Object.entries(users).map(([key, value]) => <option key={key} value={key}>{key} · {value.name} · {value.role}</option>)}
        </select>
        <button className="ui-button ui-button--secondary" disabled={busy} onClick={() => void load().catch(error => setMessage(apiErrorMessage(error, "加载失败")))}><RefreshCw size={15}/>刷新</button>
      </div>
      {message && <p role="status" className="text-sm text-[#636366]">{message}</p>}
      {account && <>
        {fixed ? <p className="text-sm text-[#248A3D]">超级管理员和销售小A固定保留全部经营管理权限。</p> : <>
          <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">{catalog.map(permission => <label key={permission.key} className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5" disabled={busy} checked={selected.includes(permission.key)} onChange={e => setSelected(current => e.target.checked ? [...current, permission.key] : current.filter(key => key !== permission.key))}/>{permission.label}
          </label>)}</div>
          <div className="flex flex-wrap gap-2"><input aria-label="授权调整原因" className="h-10 min-w-0 flex-1 border border-[#C7C7CC] px-3 text-sm" value={reason} maxLength={1000} onChange={e => setReason(e.target.value)} placeholder="授权调整原因（必填）"/>
            <button className="ui-button ui-button--primary" disabled={busy || !reason.trim()} onClick={() => void save()}><Save size={15}/>保存权限</button></div>
        </>}
        <details className="border-t border-[#E5E5EA] pt-3"><summary className="cursor-pointer text-sm">授权记录（{events.length}）</summary><div className="mt-3 divide-y divide-[#E5E5EA]">{events.map((event, index) => <div key={index} className="space-y-1 py-3 text-xs text-[#636366]">
          <p>{event.created_at} · 操作账号 {event.operator_uid} · {event.reason}</p>
          <p>增加：{catalog.filter(p => event.after.includes(p.key) && !event.before.includes(p.key)).map(p => p.label).join("、") || "无"}</p>
          <p>移除：{catalog.filter(p => event.before.includes(p.key) && !event.after.includes(p.key)).map(p => p.label).join("、") || "无"}</p>
        </div>)}</div></details>
      </>}
    </div>
  </details>;
}
