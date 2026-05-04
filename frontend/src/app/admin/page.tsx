"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { getUsers, createUser, deleteUser, resetPassword, getAllTasks } from "@/lib/api";
import type { UserInfo, TaskItem } from "@/lib/types";

export default function AdminPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  // ---- 用户管理 ----
  const [users, setUsers] = useState<Record<string, UserInfo>>({});
  const [uid, setUid] = useState("");
  const [name, setName] = useState("");
  const [pwd, setPwd] = useState("");
  const [role, setRole] = useState("录入员");
  const [userMsg, setUserMsg] = useState("");

  // ---- 密码重置 ----
  const [resetUid, setResetUid] = useState<string | null>(null);
  const [newPwd, setNewPwd] = useState("");

  // ---- 任务总览 ----
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [taskLoading, setTaskLoading] = useState(false);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  const roleOptions = [
    { value: "录入员", label: "录入员" },
    { value: "绘图员", label: "绘图员" },
    { value: "初审员", label: "初审员" },
    { value: "总工", label: "总工" },
    { value: "超级管理员", label: "超级管理员" },
  ];

  const fetchUsers = async () => {
    try {
      const res = await getUsers();
      setUsers(res.users);
    } catch {}
  };

  const fetchTasks = async () => {
    setTaskLoading(true);
    try {
      const res = await getAllTasks();
      setTasks(res.tasks);
    } catch {}
    setTaskLoading(false);
  };

  useEffect(() => {
    if (!authLoading && user?.role === "超级管理员") {
      fetchUsers();
      fetchTasks();
    }
  }, [authLoading, user]);

  // 未登录或非管理员
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F2F2F7]">
        <p className="text-[#8E8E93] text-sm">加载中...</p>
      </div>
    );
  }

  if (!user) {
    router.push("/");
    return null;
  }

  if (user.role !== "超级管理员") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F2F2F7]">
        <div className="text-center">
          <p className="text-2xl mb-2">🔒</p>
          <p className="text-[#1C1C1E] font-semibold text-lg">无访问权限</p>
          <p className="text-[#8E8E93] text-sm mt-1">仅超级管理员可访问后台管理</p>
          <button
            onClick={() => router.push("/dashboard")}
            className="mt-4 px-5 py-2 rounded-lg bg-[#007AFF] text-white font-medium text-sm hover:opacity-90 transition-all"
          >
            返回工作台
          </button>
        </div>
      </div>
    );
  }

  const handleCreateUser = async () => {
    if (!uid || !name || !pwd) {
      setUserMsg("请填写完整信息");
      return;
    }
    try {
      await createUser({ uid, pwd, role, name });
      setUserMsg(`账号 ${uid} 已保存`);
      setUid(""); setName(""); setPwd("");
      fetchUsers();
    } catch { setUserMsg("保存失败"); }
  };

  const handleResetPassword = async () => {
    if (!resetUid || !newPwd) return;
    try {
      await resetPassword(resetUid, newPwd);
      setUserMsg(`已重置 ${resetUid} 的密码`);
      setResetUid(null);
      setNewPwd("");
    } catch { setUserMsg("重置失败"); }
  };

  const handleDeleteUser = async (u: string) => {
    if (u === "admin") return;
    try {
      await deleteUser(u);
      fetchUsers();
    } catch {}
  };

  const statusColor = (s: string) => {
    if (s === "已通过") return "bg-[#E5FBE5] text-[#34C759]";
    if (s === "待修改") return "bg-[#FFE5E5] text-[#FF3B30]";
    if (s.includes("待")) return "bg-[#FFF3E0] text-[#FF9500]";
    return "bg-[#F2F2F7] text-[#8E8E93]";
  };

  return (
    <div className="min-h-screen bg-[#F2F2F7] px-6 py-8">
      {/* 顶部 */}
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-[28px] font-bold text-[#1C1C1E] tracking-tight">系统后台管理</h1>
            <p className="text-[#8E8E93] text-sm mt-1">账号管理 · 数据总览 · 上帝视角</p>
          </div>
          <button
            onClick={() => router.push("/dashboard")}
            className="px-4 py-2 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] text-sm font-medium hover:border-[#007AFF] hover:text-[#007AFF] transition-all"
          >
            ← 返回工作台
          </button>
        </div>

        {userMsg && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-[#E5FBE5] text-[#34C759] text-sm font-medium">
            {userMsg}
            <button onClick={() => setUserMsg("")} className="ml-3 text-[#8E8E93] hover:text-[#1C1C1E]">✕</button>
          </div>
        )}

        {/* ========== 账号管理 ========== */}
        <section className="mb-10">
          <div className="bg-white rounded-2xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden">
            {/* 卡片头部 */}
            <div className="px-6 py-5 border-b border-[#F2F2F7]">
              <h2 className="text-[20px] font-semibold text-[#1C1C1E]">账号管理</h2>
              <p className="text-[#8E8E93] text-xs mt-0.5">
                共 {Object.keys(users).length} 个账号
              </p>
            </div>

            {/* 新增账号表单 */}
            <div className="px-6 py-4 bg-[#FAFAFC] border-b border-[#F2F2F7]">
              <div className="flex flex-wrap items-end gap-3">
                <MiniInput label="账号" value={uid} onChange={setUid} placeholder="如: E" />
                <MiniInput label="姓名" value={name} onChange={setName} placeholder="如: 销售小E" />
                <MiniInput label="密码" value={pwd} onChange={setPwd} placeholder="初始密码" />
                <div>
                  <label className="block text-[11px] font-medium text-[#8E8E93] mb-1">角色</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="px-3 py-2 text-sm rounded-lg bg-white border border-[#C7C7CC] outline-none focus:border-[#007AFF]"
                  >
                    {roleOptions.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleCreateUser}
                  className="px-5 py-2 rounded-lg bg-[#007AFF] text-white font-medium text-sm hover:opacity-90 transition-all"
                >
                  + 添加账号
                </button>
              </div>
            </div>

            {/* 用户表格 */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#F2F2F7] bg-[#FAFAFC]">
                    <Th>账号</Th>
                    <Th>姓名</Th>
                    <Th>角色</Th>
                    <Th>默认模块</Th>
                    <Th>密码</Th>
                    <Th className="text-right">操作</Th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(users).map(([uId, info]) => (
                    <tr key={uId} className="border-b border-[#F2F2F7] hover:bg-[#FAFAFC] transition-colors">
                      <Td><span className="font-semibold text-[#1C1C1E]">{uId}</span></Td>
                      <Td>{info.name}</Td>
                      <Td>
                        <span className="px-2 py-0.5 rounded-md bg-[#F2F2F7] text-[#1C1C1E] text-xs font-medium">
                          {info.role}
                        </span>
                      </Td>
                      <Td className="text-[#8E8E93]">{info.default_module}</Td>
                      <Td>
                        <span className="font-mono text-[#8E8E93] tracking-wider">
                          {"•".repeat(Math.min(info.password.length, 8))}
                        </span>
                      </Td>
                      <Td>
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => { setResetUid(uId); setNewPwd(""); }}
                            className="px-3 py-1 rounded-md text-xs font-medium text-[#007AFF] hover:bg-[#E8F2FF] transition-all"
                          >
                            重置密码
                          </button>
                          {uId !== "admin" ? (
                            <button
                              onClick={() => handleDeleteUser(uId)}
                              className="px-3 py-1 rounded-md text-xs font-medium text-[#FF3B30] hover:bg-[#FFF0F0] transition-all"
                            >
                              删除
                            </button>
                          ) : (
                            <span className="text-xs text-[#C7C7CC]">内置</span>
                          )}
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 重置密码弹窗 */}
          {resetUid && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
              <div className="bg-white rounded-2xl px-6 py-5 shadow-2xl max-w-sm w-full mx-4">
                <h3 className="text-lg font-semibold text-[#1C1C1E] mb-4">
                  重置密码 — {resetUid}
                </h3>
                <input
                  type="text"
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  placeholder="输入新密码"
                  className="w-full px-4 py-2.5 text-sm rounded-lg bg-[#FAFAFC] border border-[#C7C7CC] outline-none focus:border-[#007AFF] mb-4"
                  autoFocus
                />
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setResetUid(null)}
                    className="px-4 py-2 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] text-sm font-medium hover:border-[#007AFF] transition-all"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleResetPassword}
                    disabled={!newPwd}
                    className="px-5 py-2 rounded-lg bg-[#007AFF] text-white font-medium text-sm hover:opacity-90 disabled:opacity-40 transition-all"
                  >
                    确认重置
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ========== 数据总览 ========== */}
        <section>
          <div className="bg-white rounded-2xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden">
            <div className="px-6 py-5 border-b border-[#F2F2F7] flex items-center justify-between">
              <div>
                <h2 className="text-[20px] font-semibold text-[#1C1C1E]">订单数据总览</h2>
                <p className="text-[#8E8E93] text-xs mt-0.5">
                  全部 {tasks.length} 条记录 — 纯文本上帝视角
                </p>
              </div>
              <button
                onClick={fetchTasks}
                disabled={taskLoading}
                className="px-4 py-2 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] text-xs font-medium hover:border-[#007AFF] transition-all"
              >
                {taskLoading ? "刷新中..." : "刷新数据"}
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#F2F2F7] bg-[#FAFAFC]">
                    <Th>ID</Th>
                    <Th>日期</Th>
                    <Th>客户</Th>
                    <Th>项目</Th>
                    <Th>门型</Th>
                    <Th>洞口尺寸</Th>
                    <Th>制单人</Th>
                    <Th>状态</Th>
                    <Th className="text-right">详情</Th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-6 py-12 text-center text-[#8E8E93] text-sm">
                        {taskLoading ? "加载中..." : "暂无订单数据"}
                      </td>
                    </tr>
                  ) : (
                    tasks.map((t) => (
                      <>
                        <tr
                          key={t.id}
                          className="border-b border-[#F2F2F7] hover:bg-[#FAFAFC] transition-colors cursor-pointer"
                          onClick={() => setExpandedTask(expandedTask === t.id ? null : t.id)}
                        >
                          <Td><span className="font-mono text-xs text-[#8E8E93]">{t.id}</span></Td>
                          <Td>{t.date}</Td>
                          <Td className="font-medium text-[#1C1C1E]">{t.customer}</Td>
                          <Td className="max-w-[140px] truncate">{t.project}</Td>
                          <Td>{t.door_type}</Td>
                          <Td className="font-mono text-xs">{t.size}</Td>
                          <Td className="text-[#8E8E93]">{t.params?.hhxd || "-"}</Td>
                          <Td>
                            <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium ${statusColor(t.status)}`}>
                              {t.status}
                            </span>
                          </Td>
                          <Td>
                            <div className="flex justify-end">
                              <span className="text-xs text-[#007AFF] font-medium">
                                {expandedTask === t.id ? "收起 ↑" : "展开 ↓"}
                              </span>
                            </div>
                          </Td>
                        </tr>
                        {/* 展开行 */}
                        {expandedTask === t.id && (
                          <tr key={`${t.id}-detail`} className="bg-[#FAFAFC] border-b border-[#F2F2F7]">
                            <td colSpan={9} className="px-6 py-4">
                              <div className="grid grid-cols-3 md:grid-cols-5 gap-3 text-xs">
                                <KV label="订单号" value={t.params?.ddh || "-"} />
                                <KV label="材质" value={t.params?.zzcl || "-"} />
                                <KV label="颜色" value={t.params?.ys || "-"} />
                                <KV label="开向" value={`${t.params?.sel_kx || ""}${t.params?.sel_nk || ""}`} />
                                <KV label="数量" value={t.params?.sl || "-"} />
                                <KV label="下槛" value={t.params?.threshold_type || "-"} />
                                <KV label="拉手(正)" value={t.params?.zmls || "-"} />
                                <KV label="拉手(反)" value={t.params?.fmls || "-"} />
                                <KV label="合页" value={t.params?.sel_hys || "-"} />
                                <KV label="门扇厚" value={t.params?.mshd ? `${t.params.mshd}mm` : "-"} />
                                <KV label="气窗" value={t.params?.sel_qc || "无"} />
                                <KV label="门楣" value={t.params?.has_mm ? `${t.params.mm_height}mm` : "无"} />
                                <KV label="立柱" value={t.params?.has_pillar ? `有 (${t.params.pillar_width_str})` : "无"} />
                                <KV label="外包套" value={t.params?.has_outer ? `${t.params.trim_front_in}mm` : "无"} />
                                <KV label="内包套" value={t.params?.has_inner ? `${t.params.trim_back_in}mm` : "无"} />
                                <KV label="包装" value={t.params?.sel_bz || "-"} />
                                <KV label="沟通记录" value={t.ref_text || "无"} isWide />
                                <KV label="审核意见" value={t.review_feedback || "无"} isWide />
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

// ===================== 微型组件 =====================
function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-5 py-3 text-left text-[11px] font-semibold text-[#8E8E93] uppercase tracking-wider ${className || ""}`}>
      {children}
    </th>
  );
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <td className={`px-5 py-3 text-sm text-[#1C1C1E] ${className || ""}`}>
      {children}
    </td>
  );
}

function MiniInput({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-[11px] font-medium text-[#8E8E93] mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-36 px-3 py-2 text-sm rounded-lg bg-white border border-[#C7C7CC] outline-none focus:border-[#007AFF]"
      />
    </div>
  );
}

function KV({ label, value, isWide }: { label: string; value: string; isWide?: boolean }) {
  return (
    <div className={isWide ? "col-span-full" : ""}>
      <span className="text-[#8E8E93]">{label}</span>
      <p className="text-[#1C1C1E] font-medium mt-0.5 break-all">{value}</p>
    </div>
  );
}
