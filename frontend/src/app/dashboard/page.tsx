"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  getTasks, getTask, createTask, updateTask, deleteTask,
  generateCad, downloadCadBlob,
} from "@/lib/api";
import { DEFAULT_FORM_DATA } from "@/lib/types";
import type { TaskItem, DoorFormData } from "@/lib/types";
import DoorForm from "@/components/DoorForm";
import TaskCard from "@/components/TaskCard";
import StatusBadge from "@/components/StatusBadge";
import ClipboardUpload from "@/components/ClipboardUpload";
import { Thumbnail } from "@/components/ImageModal";

export default function DashboardPage() {
  const { module, user } = useAuth();
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<TaskItem | null>(null);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<DoorFormData>(DEFAULT_FORM_DATA);
  const [refText, setRefText] = useState("");
  const [refImgB64, setRefImgB64] = useState<string | null>(null);
  const [uploadImgB64, setUploadImgB64] = useState<string | null>(null);
  const [reviewFeedback, setReviewFeedback] = useState("");
  const [cadBlob, setCadBlob] = useState<Blob | null>(null);
  const [cadLoading, setCadLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      let params: { status?: string } = {};
      if (module === "图纸绘制") params.status = "待绘制";
      else if (module === "图纸初审") params.status = "待初审";
      else if (module === "图纸终审") params = {};
      const res = await getTasks(params);
      if (module === "图纸终审") {
        setTasks(res.tasks.filter((t) => t.status === "待终审" || t.status === "已通过"));
      } else {
        setTasks(res.tasks);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }, [module]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    if (activeTaskId) {
      getTask(activeTaskId).then((t) => {
        setActiveTask(t);
        if (t.params) setFormData({ ...DEFAULT_FORM_DATA, ...t.params });
        setRefText(t.ref_text || "");
        setRefImgB64(t.ref_img_b64 || null);
        setUploadImgB64(t.drawing_img_b64 || null);
        setReviewFeedback(t.review_feedback || "");
        setCadBlob(null);
      });
    }
  }, [activeTaskId]);

  const backToList = () => {
    setActiveTaskId(null);
    setActiveTask(null);
    setFormData(DEFAULT_FORM_DATA);
    setRefText("");
    setRefImgB64(null);
    setUploadImgB64(null);
    setReviewFeedback("");
    setCadBlob(null);
    setMessage(null);
  };

  const flash = (text: string, type: "success" | "error" | "info") => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 4000);
  };

  // ===================== 录入模块 =====================
  const handleSubmitOrder = async () => {
    try {
      await createTask({ params: formData, ref_text: refText, ref_img_b64: refImgB64 });
      flash("订单提交成功，已流转至绘图部！", "success");
      setFormData(DEFAULT_FORM_DATA);
      setRefText("");
      setRefImgB64(null);
      fetchTasks();
    } catch { flash("提交失败", "error"); }
  };

  const handleQuickCad = async () => {
    setCadLoading(true);
    try {
      const blob = await generateCad(formData);
      setCadBlob(blob);
      downloadCadBlob(blob, `排版图纸_${formData.dhdw || "unnamed"}.dxf`);
      flash("CAD 生成完成！", "success");
    } catch { flash("CAD 生成失败", "error"); }
    setCadLoading(false);
  };

  // ===================== 绘制模块 =====================
  const handleGenerateCad = async () => {
    setCadLoading(true);
    try {
      const blob = await generateCad(formData);
      setCadBlob(blob);
      downloadCadBlob(blob, `基准图纸_${activeTaskId}.dxf`);
      flash("基准 CAD 底图已生成", "success");
    } catch { flash("CAD 生成失败", "error"); }
    setCadLoading(false);
  };

  const handleSubmitDrawing = async () => {
    if (!activeTaskId || !uploadImgB64) {
      flash("请先上传深化图纸图片", "error");
      return;
    }
    try {
      await updateTask(activeTaskId, {
        drawing_img_b64: uploadImgB64,
        status: "待初审",
        params: formData,
      });
      flash("成功流转至初审！", "success");
      backToList();
      fetchTasks();
    } catch { flash("提交失败", "error"); }
  };

  // ===================== 初审 / 终审模块 =====================
  const handleReject = async (targetStatus: string) => {
    if (!activeTaskId) return;
    try {
      await updateTask(activeTaskId, { status: targetStatus, review_feedback: reviewFeedback });
      flash("已打回修改", "success");
      backToList();
      fetchTasks();
    } catch { flash("操作失败", "error"); }
  };

  const handleApprove = async () => {
    if (!activeTaskId) return;
    const nextStatus = module === "图纸初审" ? "待终审" : "已通过";
    const msg = module === "图纸初审" ? "初审通过，已转终审" : "终审通过，可下发生产";
    try {
      await updateTask(activeTaskId, { status: nextStatus, review_feedback: msg });
      flash(msg, "success");
      backToList();
      fetchTasks();
    } catch { flash("操作失败", "error"); }
  };

  // ===================== 通用背景 =====================
  if (module === "后台管理") {
    return <AdminPanel />;
  }

  return (
    <div>
      {message && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
          message.type === "success" ? "bg-[#E5FBE5] text-[#34C759]" :
          message.type === "error" ? "bg-[#FFE5E5] text-[#FF3B30]" :
          "bg-[#F2F2F7] text-[#1C1C1E]"
        }`}>
          {message.text}
        </div>
      )}

      {/* ---------- 任务详情模式 ---------- */}
      {activeTaskId && activeTask ? (
        <div>
          {/* 返回 + 标题 */}
          <div className="flex items-center gap-4 mb-4">
            <button
              onClick={backToList}
              className="px-4 py-2 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] text-sm font-medium hover:border-[#007AFF] hover:text-[#007AFF] transition-colors"
            >
              ← 返回列表
            </button>
            <h4 className="text-lg font-semibold text-[#1C1C1E] m-0">
              正在处理：{activeTask.customer} - {activeTask.project} <StatusBadge status={activeTask.status} />
            </h4>
          </div>

          {/* 客户沟通记录 */}
          {(activeTask.ref_text || activeTask.ref_img_b64) && (
            <details className="mb-4 bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden">
              <summary className="px-5 py-3 font-medium text-[#007AFF] cursor-pointer select-none">
                查看前端客户沟通记录与参考图
              </summary>
              <div className="px-5 pb-4">
                {activeTask.ref_text && <p className="text-[#8E8E93] text-sm mb-3">{activeTask.ref_text}</p>}
                {activeTask.ref_img_b64 && <Thumbnail b64={activeTask.ref_img_b64} width={250} />}
              </div>
            </details>
          )}

          {/* 驳回意见 */}
          {activeTask.status === "待修改" && activeTask.review_feedback && (
            <div className="mb-4 p-4 bg-[#FFE5E5] text-[#FF3B30] rounded-lg text-sm font-medium">
              {activeTask.review_feedback}
            </div>
          )}

          {/* 表单 */}
          <DoorForm data={formData} onChange={setFormData} />

          {/* 模块特有操作 */}
          <div className="mt-6 space-y-4">
            {/* 绘制模块 */}
            {module === "图纸绘制" && (
              <>
                <Card title="第 1 步：生成基准 CAD 底图">
                  <button
                    onClick={handleGenerateCad}
                    disabled={cadLoading}
                    className="w-full py-2.5 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] font-medium text-sm hover:border-[#007AFF] hover:text-[#007AFF] transition-all disabled:opacity-50"
                  >
                    {cadLoading ? "生成中..." : "生成并下载 DXF 进行深化"}
                  </button>
                  {cadBlob && (
                    <button
                      onClick={() => downloadCadBlob(cadBlob!, `基准图纸_${activeTaskId}.dxf`)}
                      className="w-full mt-2 py-2.5 rounded-lg bg-[#007AFF] text-white font-semibold text-sm transition-all"
                    >
                      确认下载 DXF
                    </button>
                  )}
                </Card>

                <Card title="第 2 步：上传深化图纸并提交初审">
                  <ClipboardUpload onImage={setUploadImgB64} />
                  {uploadImgB64 && <Thumbnail b64={uploadImgB64} width={250} />}
                  <button
                    onClick={handleSubmitDrawing}
                    className="w-full mt-3 py-2.5 rounded-lg bg-[#007AFF] text-white font-semibold text-sm transition-all hover:opacity-90"
                  >
                    提交至【图纸初审】
                  </button>
                </Card>
              </>
            )}

            {/* 初审模块 */}
            {module === "图纸初审" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-[17px] font-semibold text-[#1C1C1E] mb-3">图纸全屏预览</h4>
                  {activeTask.drawing_img_b64 ? (
                    <Thumbnail b64={activeTask.drawing_img_b64} width={400} />
                  ) : (
                    <p className="text-[#FF9500] text-sm">绘图员未上传深化图。</p>
                  )}
                  {activeTask.ref_img_b64 && (
                    <details className="mt-3">
                      <summary className="text-[#007AFF] text-sm cursor-pointer">查看参考图</summary>
                      <div className="mt-2"><Thumbnail b64={activeTask.ref_img_b64} width={200} /></div>
                    </details>
                  )}
                </div>
                <div className="space-y-4">
                  <Card title="核心参数">
                    <p className="text-sm text-[#8E8E93]">
                      客户: {activeTask.params?.dhdw} | 项目: {activeTask.params?.gdmc}<br />
                      门型: {activeTask.params?.door_type} | 洞口: {activeTask.params?.dw}x{activeTask.params?.dh}<br />
                      开向: {activeTask.params?.sel_kx}{activeTask.params?.sel_nk}<br />
                      材质: {activeTask.params?.zzcl} | 颜色: {activeTask.params?.ys}
                    </p>
                  </Card>
                  <Card title="初审意见">
                    <textarea
                      value={reviewFeedback}
                      onChange={(e) => setReviewFeedback(e.target.value)}
                      placeholder="初审发现的问题..."
                      rows={4}
                      className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none resize-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)]"
                    />
                  </Card>
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleReject("待修改")}
                      className="flex-1 py-2.5 rounded-lg bg-[#FFF0F0] text-[#FF3B30] border border-[#FFD1D1] font-medium text-sm hover:bg-[#FF3B30] hover:text-white transition-all"
                    >
                      打回修改
                    </button>
                    <button
                      onClick={handleApprove}
                      className="flex-1 py-2.5 rounded-lg bg-[#007AFF] text-white font-semibold text-sm hover:opacity-90 transition-all"
                    >
                      初审通过 (转终审)
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 终审模块 */}
            {module === "图纸终审" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-[17px] font-semibold text-[#1C1C1E] mb-3">图纸全屏预览</h4>
                  {activeTask.drawing_img_b64 ? (
                    <Thumbnail b64={activeTask.drawing_img_b64} width={400} />
                  ) : (
                    <p className="text-[#FF9500] text-sm">绘图员未上传深化图。</p>
                  )}
                </div>
                <div className="space-y-4">
                  <Card title="核心参数">
                    <p className="text-sm text-[#8E8E93]">
                      客户: {activeTask.params?.dhdw} | 项目: {activeTask.params?.gdmc}<br />
                      门型: {activeTask.params?.door_type} | 洞口: {activeTask.params?.dw}x{activeTask.params?.dh}<br />
                      开向: {activeTask.params?.sel_kx}{activeTask.params?.sel_nk}
                    </p>
                  </Card>
                  <Card title="终审意见">
                    <textarea
                      value={reviewFeedback}
                      onChange={(e) => setReviewFeedback(e.target.value)}
                      placeholder="终审意见..."
                      rows={4}
                      className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none resize-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)]"
                    />
                  </Card>
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleReject("待修改")}
                      className="flex-1 py-2.5 rounded-lg bg-[#FFF0F0] text-[#FF3B30] border border-[#FFD1D1] font-medium text-sm hover:bg-[#FF3B30] hover:text-white transition-all"
                    >
                      打回重新绘制
                    </button>
                    <button
                      onClick={handleApprove}
                      className="flex-1 py-2.5 rounded-lg bg-[#007AFF] text-white font-semibold text-sm hover:opacity-90 transition-all"
                    >
                      终审通过 (发车间)
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ---------- 任务列表模式 ---------- */
        <div>
          {/* 录入模块 */}
          {module === "图纸信息录入" && (
            <div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div className="bg-white rounded-xl p-5 border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
                  <h4 className="text-[17px] font-semibold text-[#1C1C1E] mb-3 pb-2.5 border-b border-[#F2F2F7]">
                    客户沟通记录
                  </h4>
                  <textarea
                    value={refText}
                    onChange={(e) => setRefText(e.target.value)}
                    placeholder="在此打字或粘贴沟通要求"
                    rows={3}
                    className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none resize-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)]"
                  />
                </div>
                <div className="bg-white rounded-xl p-5 border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
                  <h4 className="text-[17px] font-semibold text-[#1C1C1E] mb-3 pb-2.5 border-b border-[#F2F2F7]">
                    参考图上传
                  </h4>
                  <ClipboardUpload onImage={setRefImgB64} />
                  {refImgB64 && <div className="mt-3"><Thumbnail b64={refImgB64} width={200} /></div>}
                </div>
              </div>

              <DoorForm data={formData} onChange={setFormData}>
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={handleSubmitOrder}
                    className="flex-1 py-3 rounded-lg bg-[#007AFF] text-white font-semibold text-sm hover:opacity-90 transition-all"
                  >
                    提交订单 (流转至绘图部)
                  </button>
                  <button
                    onClick={handleQuickCad}
                    disabled={cadLoading}
                    className="flex-1 py-3 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] font-medium text-sm hover:border-[#007AFF] hover:text-[#007AFF] transition-all disabled:opacity-50"
                  >
                    {cadLoading ? "生成中..." : "快速生成 CAD (仅下载不流转)"}
                  </button>
                </div>
              </DoorForm>
            </div>
          )}

          {/* 其他模块任务列表 */}
          {module !== "图纸信息录入" && (
            <div>
              <h4 className="text-lg font-semibold text-[#1C1C1E] mb-4">
                {module === "图纸绘制" && "待绘制任务"}
                {module === "图纸初审" && "待初审任务"}
                {module === "图纸终审" && "待终审 / 已通过任务"}
              </h4>
              {loading ? (
                <p className="text-[#8E8E93] text-sm">加载中...</p>
              ) : tasks.length === 0 ? (
                <p className="text-[#8E8E93] text-sm">暂无待处理任务</p>
              ) : (
                tasks.map((t) => (
                  <TaskCard
                    key={t.id}
                    task={t}
                    onClick={(task) => {
                      setActiveTaskId(task.id);
                    }}
                    onDelete={module === "图纸绘制" ? async (task) => {
                      await deleteTask(task.id);
                      fetchTasks();
                    } : undefined}
                  />
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 白色悬浮卡片 */
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-5">
      <h4 className="text-[17px] font-semibold text-[#1C1C1E] mb-3 pb-2.5 border-b border-[#F2F2F7]">{title}</h4>
      {children}
    </div>
  );
}

/** 后台管理面板 */
function AdminPanel() {
  const [users, setUsers] = useState<Record<string, { password: string; role: string; name: string }>>({});
  const [uid, setUid] = useState("");
  const [name, setName] = useState("");
  const [pwd, setPwd] = useState("");
  const [role, setRole] = useState("录入员");

  const fetchUsers = async () => {
    try {
      const { getUsers: apiGetUsers } = await import("@/lib/api");
      const res = await apiGetUsers();
      setUsers(res.users);
    } catch {}
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleSave = async () => {
    if (!uid || !name || !pwd) return;
    try {
      const { createUser: apiCreateUser } = await import("@/lib/api");
      await apiCreateUser({ uid, pwd, role, name });
      fetchUsers();
      setUid(""); setName(""); setPwd("");
    } catch {}
  };

  const handleDelete = async (u: string) => {
    try {
      const { deleteUser: apiDeleteUser } = await import("@/lib/api");
      await apiDeleteUser(u);
      fetchUsers();
    } catch {}
  };

  return (
    <div>
      <h3 className="text-xl font-semibold text-[#1C1C1E] mb-4">系统后台管理</h3>
      <Card title="添加/更新账号">
        <div className="grid grid-cols-4 gap-3">
          <input
            placeholder="账号" value={uid}
            onChange={(e) => setUid(e.target.value)}
            className="px-3 py-2 rounded-md bg-[#FAFAFC] border border-[#C7C7CC] text-sm outline-none focus:border-[#007AFF]"
          />
          <input
            placeholder="姓名" value={name}
            onChange={(e) => setName(e.target.value)}
            className="px-3 py-2 rounded-md bg-[#FAFAFC] border border-[#C7C7CC] text-sm outline-none focus:border-[#007AFF]"
          />
          <input
            placeholder="密码" value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            className="px-3 py-2 rounded-md bg-[#FAFAFC] border border-[#C7C7CC] text-sm outline-none focus:border-[#007AFF]"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="px-3 py-2 rounded-md bg-[#FAFAFC] border border-[#C7C7CC] text-sm outline-none focus:border-[#007AFF]"
          >
            {["录入员", "绘图员", "初审员", "总工", "超级管理员"].map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleSave}
          className="mt-3 px-6 py-2 rounded-lg bg-[#007AFF] text-white font-semibold text-sm hover:opacity-90 transition-all"
        >
          保存账号
        </button>
      </Card>

      <h4 className="text-lg font-semibold text-[#1C1C1E] mt-6 mb-3">当前用户列表</h4>
      {Object.entries(users).map(([uId, info]) => (
        <div key={uId} className="flex items-center justify-between bg-white rounded-lg px-5 py-3 mb-2 border border-black/5 shadow-sm">
          <span className="text-sm">
            <strong>{info.name}</strong> (账号: {uId}) | 角色: {info.role} | 密码: {info.password}
          </span>
          {uId !== "admin" ? (
            <button
              onClick={() => handleDelete(uId)}
              className="px-3 py-1 rounded-md bg-[#FFF0F0] text-[#FF3B30] border border-[#FFD1D1] text-xs font-medium hover:bg-[#FF3B30] hover:text-white transition-all"
            >
              删除
            </button>
          ) : (
            <span className="text-xs text-[#8E8E93]">系统内置不可删</span>
          )}
        </div>
      ))}
    </div>
  );
}
