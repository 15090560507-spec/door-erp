"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  getTasks, getTask, createTask, updateTask, deleteTask,
  generateCad, downloadCadBlob,
  getUsers, createUser as apiCreateUser, deleteUser as apiDeleteUser,
  resetPassword as apiResetPassword, getAllTasks,
} from "@/lib/api";
import { DEFAULT_FORM_DATA } from "@/lib/types";
import type { TaskItem, DoorFormData, UserInfo } from "@/lib/types";
import DoorForm from "@/components/DoorForm";
import TaskCard from "@/components/TaskCard";
import StatusBadge from "@/components/StatusBadge";
import ClipboardUpload from "@/components/ClipboardUpload";
import { Thumbnail } from "@/components/ImageModal";
import { TaskListSkeleton } from "@/components/Skeleton";
import DropdownOptionsManager from "@/components/DropdownOptionsManager";

export default function DashboardPage() {
  const { module, user } = useAuth();
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<TaskItem | null>(null);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [taskLoading, setTaskLoading] = useState(false);
  const [formData, setFormData] = useState<DoorFormData>(DEFAULT_FORM_DATA);
  const [refText, setRefText] = useState("");
  const [refImages, setRefImages] = useState<string[]>([]);
  const [uploadImgB64, setUploadImgB64] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [reviewFeedback, setReviewFeedback] = useState("");
  const [cadBlob, setCadBlob] = useState<Blob | null>(null);
  const [cadLoading, setCadLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [filterDate, setFilterDate] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const PAGE_SIZE = 20;

  // 用 ref 保存 module，避免 fetchTasks 因 module 变化而重建导致双重请求
  const moduleRef = useRef(module);
  moduleRef.current = module;

  // setTimeout 清理：防止组件卸载后更新状态
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const fetchTasks = useCallback(async (date?: string, status?: string, p: number = 0) => {
    setLoading(true);
    const m = moduleRef.current;
    try {
      let params: { status?: string; date?: string; limit: number; offset: number } = {
        limit: PAGE_SIZE,
        offset: p * PAGE_SIZE,
      };
      if (status) {
        params.status = status;
      } else if (m === "汇总看板") {
        // 汇总看板：所有进行中的任务（不含已通过）
        params.status = "待绘制,待初审,待终审,待修改";
      } else if (m === "图纸绘制") {
        // 绘图员需要看到新任务 + 被打回待修改的任务
        params.status = "待绘制,待修改";
      } else if (m === "图纸初审") {
        params.status = "待初审";
      } else if (m === "图纸终审") {
        params.status = "待终审,已通过";
      }
      if (date) params.date = date;
      const res = await getTasks(params);
      setTasks(res.tasks);
      setTotal(res.total);
    } catch (e) {
      setMessage({ text: "任务列表加载失败，请检查网络连接", type: "error" });
      setTimeout(() => setMessage(null), 4000);
    }
    setLoading(false);
  }, []); // 空依赖：fetchTasks 引用稳定

  useEffect(() => {
    setPage(0);
    fetchTasks(filterDate, filterStatus, 0);
  }, [fetchTasks, filterDate, filterStatus, module]); // module 变化时重新触发

  // 切换模块时自动返回任务列表（保留表单数据以便返回继续编辑）
  useEffect(() => {
    setActiveTaskId(null);
    setActiveTask(null);
    setTaskLoading(false);
    // 非录入模块切换时才清理（录入模块切换任务不清理表单）
    setRefText("");
    setRefImages([]);
    setUploadImgB64(null);
    setReviewFeedback("");
    setCadBlob(null);
    setMessage(null);
  }, [module]);

  useEffect(() => {
    if (activeTaskId) {
      setActiveTask(null);
      setTaskLoading(true);
      getTask(activeTaskId).then((t) => {
        setActiveTask(t);
        if (t.params) setFormData({ ...DEFAULT_FORM_DATA, ...t.params });
        setRefText(t.ref_text || "");
        setRefImages(t.ref_images || []);
        setUploadImgB64(t.drawing_img_b64 || null);
        setReviewFeedback(t.review_feedback || "");
        setCadBlob(null);
      }).finally(() => {
        setTaskLoading(false);
      });
    }
  }, [activeTaskId]);

  const backToList = () => {
    setActiveTaskId(null);
    setActiveTask(null);
    setFormData(DEFAULT_FORM_DATA);
    setRefText("");
    setRefImages([]);
    setUploadImgB64(null);
    setReviewFeedback("");
    setCadBlob(null);
    setMessage(null);
  };

  const flash = (text: string, type: "success" | "error" | "info") => {
    setMessage({ text, type });
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    flashTimerRef.current = setTimeout(() => setMessage(null), 4000);
  };

  // ===================== 录入模块 =====================
  const handleSubmitOrder = async () => {
    // 必填项校验
    const missing: string[] = [];
    if (!formData.dhdw.trim()) missing.push("订货单位");
    if (!formData.sl.trim()) missing.push("数量(樘)");
    if (!formData.zzcl.trim()) missing.push("制作材料");
    if (!formData.ys.trim()) missing.push("颜色");
    if (!formData.dw || formData.dw <= 0) missing.push("洞口总宽(W)");
    if (!formData.dh || formData.dh <= 0) missing.push("洞口总高(H)");
    if (missing.length > 0) {
      setValidationError(`请填写以下必填项：${missing.join("、")}`);
      return;
    }
    setSubmitting(true);
    try {
      await createTask({ params: formData, ref_text: refText, ref_images: refImages });
      setToast({ text: "订单提交成功，已流转至绘图部！", type: "success" });
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setToast(null), 3000);
      fetchTasks(filterDate, filterStatus);
    } catch { flash("提交失败", "error"); }
    setSubmitting(false);
  };

  const handleSaveEdit = async () => {
    if (!activeTaskId) return;
    try {
      await updateTask(activeTaskId, { params: formData, ref_text: refText, ref_images: refImages });
      const updated = await getTask(activeTaskId);
      setActiveTask(updated);
      setIsEditing(false);
      flash("修改已保存", "success");
      fetchTasks(filterDate, filterStatus);
    } catch { flash("保存失败", "error"); }
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
      fetchTasks(filterDate, filterStatus);
    } catch { flash("提交失败", "error"); }
  };

  // ===================== 初审 / 终审模块 =====================
  const handleReject = async (targetStatus: string) => {
    if (!activeTaskId) return;
    try {
      await updateTask(activeTaskId, { status: targetStatus, review_feedback: reviewFeedback });
      flash("已打回修改", "success");
      backToList();
      fetchTasks(filterDate, filterStatus);
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
      fetchTasks(filterDate, filterStatus);
    } catch { flash("操作失败", "error"); }
  };

  // ===================== 通用背景 =====================
  if (module === "后台管理") {
    return <AdminPanel />;
  }

  return (
    <div>
      {/* 居中 Toast 弹窗 — 点击任意处关闭 */}
      {toast && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 animate-in fade-in" onClick={() => setToast(null)}>
          <div className={`rounded-2xl px-8 py-6 shadow-2xl text-center max-w-sm mx-4 ${
            toast.type === "success"
              ? "bg-white text-[#1C1C1E]"
              : "bg-white text-[#FF3B30]"
          }`} onClick={(e) => e.stopPropagation()}>
            <div className="text-4xl mb-3">{toast.type === "success" ? "✅" : "❌"}</div>
            <p className="text-[17px] font-semibold">{toast.text}</p>
          </div>
        </div>
      )}

      {/* 必填项校验弹窗 — 点击任意处关闭 */}
      {validationError && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 animate-in fade-in" onClick={() => setValidationError(null)}>
          <div className="rounded-2xl px-8 py-6 shadow-2xl text-center max-w-sm mx-4 bg-white" onClick={(e) => e.stopPropagation()}>
            <div className="text-4xl mb-3">⚠️</div>
            <p className="text-[17px] font-semibold text-[#1C1C1E]">{validationError}</p>
          </div>
        </div>
      )}

      {message && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
          message.type === "success" ? "bg-[#E5FBE5] text-[#34C759]" :
          message.type === "error" ? "bg-[#FFE5E5] text-[#FF3B30]" :
          "bg-[#F2F2F7] text-[#1C1C1E]"
        }`}>
          {message.text}
        </div>
      )}

      {/* ---------- 任务详情加载中 ---------- */}
      {activeTaskId && taskLoading && (
        <div className="space-y-4 animate-pulse">
          <div className="flex items-center gap-4 mb-4">
            <div className="h-9 w-28 bg-[#E5E5EA] rounded-lg" />
            <div className="h-6 w-80 bg-[#E5E5EA] rounded" />
          </div>
          <div className="bg-white rounded-xl p-6 border border-black/5">
            <div className="h-5 w-48 bg-[#E5E5EA] rounded mb-4" />
            <div className="grid grid-cols-3 gap-6">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="space-y-3">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <div key={j}>
                      <div className="h-3 w-16 bg-[#E5E5EA] rounded mb-1" />
                      <div className="h-9 w-full bg-[#E5E5EA] rounded-md" />
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ---------- 任务详情模式 ---------- */}
      {activeTaskId && activeTask && (
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
            <div className="ml-auto flex gap-2">
              {!isEditing ? (
                <button
                  onClick={() => setIsEditing(true)}
                  className="px-4 py-2 rounded-lg bg-white text-[#007AFF] border border-[#007AFF] text-sm font-medium hover:bg-[#F0F8FF] transition-colors"
                >
                  编辑
                </button>
              ) : (
                <>
                  <button
                    onClick={handleSaveEdit}
                    className="px-4 py-2 rounded-lg bg-[#007AFF] text-white text-sm font-semibold hover:opacity-90 transition-all"
                  >
                    保存修改
                  </button>
                  <button
                    onClick={() => { setIsEditing(false); if (activeTask.params) setFormData({ ...DEFAULT_FORM_DATA, ...activeTask.params }); setRefText(activeTask.ref_text || ""); setRefImages(activeTask.ref_images || []); }}
                    className="px-4 py-2 rounded-lg bg-[#F2F2F7] text-[#8E8E93] text-sm font-medium hover:bg-[#E5E5EA] transition-colors"
                  >
                    取消
                  </button>
                </>
              )}
            </div>
          </div>

          {isEditing && (
            <div className="mb-4 px-3 py-2 rounded-lg bg-[#FFF9E6] border border-[#FFD60A] text-[13px] text-[#8B6914]">
              编辑模式：修改表单后点击「保存修改」提交，系统将自动记录本次修改内容。
            </div>
          )}

          {/* 客户沟通记录 */}
          {(activeTask.ref_text || activeTask.ref_images?.length > 0) && (
            <details className="mb-4 bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden">
              <summary className="px-5 py-3 font-medium text-[#007AFF] cursor-pointer select-none">
                查看前端客户沟通记录与参考图
              </summary>
              <div className="px-5 pb-4">
                {activeTask.ref_text && <p className="text-[#8E8E93] text-sm mb-3">{activeTask.ref_text}</p>}
                {activeTask.ref_images?.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {activeTask.ref_images.map((img, idx) => (
                      <Thumbnail key={idx} b64={img} width={150} />
                    ))}
                  </div>
                )}
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
                  {activeTask.ref_images?.length > 0 && (
                    <details className="mt-3">
                      <summary className="text-[#007AFF] text-sm cursor-pointer">查看参考图 ({activeTask.ref_images.length}张)</summary>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {activeTask.ref_images.map((img, idx) => (
                          <Thumbnail key={idx} b64={img} width={150} />
                        ))}
                      </div>
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
      )}

      {/* ---------- 任务列表模式 ---------- */}
          {/* 修改记录 */}
          {activeTask.history && activeTask.history.length > 0 && (
            <details className="mt-6 bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden">
              <summary className="px-5 py-3 font-medium text-[#8E8E93] cursor-pointer select-none">
                修改记录 ({activeTask.history.length})
              </summary>
              <div className="px-5 pb-4 space-y-3">
                {[...activeTask.history].reverse().map((h, i) => (
                  <div key={i} className="border-l-2 border-[#007AFF] pl-3">
                    <div className="text-xs text-[#8E8E93] mb-1">
                      {h.modified_by} · {h.modified_at}
                    </div>
                    {h.changes.map((c, j) => (
                      <div key={j} className="text-[13px] text-[#48484A] leading-relaxed">
                        <span className="font-medium">{c.field}</span>: <span className="text-[#FF3B30] line-through">{c.old}</span> → <span className="text-[#248A3D]">{c.new}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {!activeTaskId && (
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
                  <ClipboardUpload onImages={setRefImages} images={refImages} />
                  {refImages.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {refImages.map((img, idx) => (
                        <div key={idx} className="relative group">
                          <Thumbnail b64={img} width={120} />
                          <button
                            onClick={() => setRefImages(refImages.filter((_, i) => i !== idx))}
                            className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                          >x</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <DoorForm data={formData} onChange={setFormData} />

              <div className="grid grid-cols-8 gap-3 mt-6">
                <button
                  onClick={handleSubmitOrder}
                  disabled={submitting}
                  className="col-span-3 py-3 rounded-lg bg-[#007AFF] text-white font-semibold text-base hover:opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? "提交中..." : "提交订单 (流转至绘图部)"}
                </button>
                <button
                  onClick={handleQuickCad}
                  disabled={cadLoading}
                  className="col-span-3 py-3 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] font-medium text-base hover:border-[#007AFF] hover:text-[#007AFF] transition-all disabled:opacity-50"
                >
                  {cadLoading ? "生成中..." : "快速生成 CAD (仅下载不流转)"}
                </button>
                <button
                  onClick={() => { setFormData(DEFAULT_FORM_DATA); setRefText(""); setRefImages([]); }}
                  className="col-span-2 py-3 rounded-lg bg-[#F2F2F7] text-[#8E8E93] font-medium text-sm hover:bg-[#E5E5EA] hover:text-[#1C1C1E] transition-all"
                >
                  清空表单
                </button>
              </div>
            </div>
          )}

          {/* 其他模块任务列表 */}
          {module !== "图纸信息录入" && (
            <div>
              {/* 统计概览卡片 */}
              {!filterDate && !filterStatus && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  {module === "图纸绘制" && (
                    <>
                      <StatCard label="待绘制" count={total} color="bg-[#E8E8ED] text-[#48484A]" />
                      <StatCard label="待修改" count={tasks.filter(t => t.status === "待修改").length} color="bg-[#FFEBEB] text-[#CC2F2A]" />
                      <StatCard label="今日新增" count={tasks.filter(t => t.date === new Date().toISOString().slice(0,10).replace(/-/g,".")).length} color="bg-[#E5F9E5] text-[#248A3D]" />
                    </>
                  )}
                  {module === "图纸初审" && (
                    <>
                      <StatCard label="待初审" count={total} color="bg-[#FFF3E0] text-[#CC7A00]" />
                      <StatCard label="今日提交" count={tasks.filter(t => t.date === new Date().toISOString().slice(0,10).replace(/-/g,".")).length} color="bg-[#E8E8ED] text-[#48484A]" />
                    </>
                  )}
                  {module === "图纸终审" && (
                    <>
                      <StatCard label="待终审" count={tasks.filter(t => t.status === "待终审").length} color="bg-[#FFF3E0] text-[#CC7A00]" />
                      <StatCard label="已通过" count={tasks.filter(t => t.status === "已通过").length} color="bg-[#E5F9E5] text-[#248A3D]" />
                    </>
                  )}
                  {module === "汇总看板" && (
                    <>
                      <StatCard label="待绘制" count={tasks.filter(t => t.status === "待绘制").length} color="bg-[#E8E8ED] text-[#48484A]" />
                      <StatCard label="待初审" count={tasks.filter(t => t.status === "待初审").length} color="bg-[#FFF3E0] text-[#CC7A00]" />
                      <StatCard label="待终审" count={tasks.filter(t => t.status === "待终审").length} color="bg-[#FFF3E0] text-[#CC7A00]" />
                      <StatCard label="待修改" count={tasks.filter(t => t.status === "待修改").length} color="bg-[#FFEBEB] text-[#CC2F2A]" />
                    </>
                  )}
                </div>
              )}

              {/* 筛选栏 */}
              <div className="flex flex-wrap items-center gap-3 mb-4 bg-white rounded-xl border border-black/5 shadow-sm px-5 py-3">
                <label className="text-[13px] font-medium text-[#8E8E93]">筛选:</label>
                <input
                  type="date"
                  value={filterDate ? filterDate.replace(/\./g, "-") : ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    setFilterDate(v ? v.replace(/-/g, ".") : "");
                  }}
                  className="px-3 py-1.5 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none focus:border-[#007AFF]"
                />
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="px-3 py-1.5 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none focus:border-[#007AFF]"
                >
                  <option value="">全部状态</option>
                  <option value="待绘制">待绘制</option>
                  <option value="待初审">待初审</option>
                  <option value="待终审">待终审</option>
                  <option value="待修改">待修改</option>
                  <option value="已通过">已通过</option>
                </select>
                {(filterDate || filterStatus) && (
                  <button
                    onClick={() => { setFilterDate(""); setFilterStatus(""); }}
                    className="px-3 py-1.5 text-xs text-[#007AFF] font-medium hover:underline"
                  >
                    清除筛选
                  </button>
                )}
              </div>

              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-semibold text-[#1C1C1E]">
                  {module === "汇总看板" && "全部进行中任务"}
                  {module === "图纸绘制" && "待绘制 / 待修改任务"}
                  {module === "图纸初审" && "待初审任务"}
                  {module === "图纸终审" && "待终审 / 已通过任务"}
                  {(filterDate || filterStatus) && " (已筛选)"}
                  {total > 0 && <span className="ml-2 text-sm font-normal text-[#8E8E93]">共 {total} 条</span>}
                </h4>
                {total > PAGE_SIZE && (
                  <div className="flex items-center gap-2 text-sm">
                    <button
                      disabled={page === 0}
                      onClick={() => { setPage(page - 1); fetchTasks(filterDate, filterStatus, page - 1); }}
                      className="px-3 py-1 rounded-md border border-[#C7C7CC] disabled:opacity-30 disabled:cursor-not-allowed hover:border-[#007AFF] transition-colors"
                    >
                      ← 上一页
                    </button>
                    <span className="text-[#8E8E93]">{page + 1} / {Math.ceil(total / PAGE_SIZE)}</span>
                    <button
                      disabled={(page + 1) * PAGE_SIZE >= total}
                      onClick={() => { setPage(page + 1); fetchTasks(filterDate, filterStatus, page + 1); }}
                      className="px-3 py-1 rounded-md border border-[#C7C7CC] disabled:opacity-30 disabled:cursor-not-allowed hover:border-[#007AFF] transition-colors"
                    >
                      下一页 →
                    </button>
                  </div>
                )}
              </div>
              {loading ? (
                <TaskListSkeleton count={5} />
              ) : tasks.length === 0 ? (
                <div className="text-center py-10 text-[#8E8E93]">
                  <div className="text-4xl mb-3">📭</div>
                  <p className="text-sm">暂无待处理任务</p>
                </div>
              ) : (
                <div>
                  {tasks.map((t) => (
                    <TaskCard
                      key={t.id}
                      task={t}
                      onClick={(task) => {
                        setActiveTaskId(task.id);
                      }}
                      onDelete={module === "图纸绘制" ? async (task) => {
                        await deleteTask(task.id);
                        fetchTasks(filterDate, filterStatus, page);
                      } : undefined}
                    />
                  ))}
                  {total > PAGE_SIZE && (
                    <div className="flex items-center justify-center gap-2 mt-4 text-sm">
                      <button
                        disabled={page === 0}
                        onClick={() => { setPage(page - 1); fetchTasks(filterDate, filterStatus, page - 1); }}
                        className="px-4 py-2 rounded-lg border border-[#C7C7CC] disabled:opacity-30 disabled:cursor-not-allowed hover:border-[#007AFF] transition-colors"
                      >
                        ← 上一页
                      </button>
                      <span className="text-[#8E8E93] px-2">{page + 1} / {Math.ceil(total / PAGE_SIZE)}</span>
                      <button
                        disabled={(page + 1) * PAGE_SIZE >= total}
                        onClick={() => { setPage(page + 1); fetchTasks(filterDate, filterStatus, page + 1); }}
                        className="px-4 py-2 rounded-lg border border-[#C7C7CC] disabled:opacity-30 disabled:cursor-not-allowed hover:border-[#007AFF] transition-colors"
                      >
                        下一页 →
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 统计概览卡片 */
function StatCard({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className={`rounded-xl p-4 ${color} bg-opacity-15`}>
      <div className="text-[11px] font-medium opacity-70">{label}</div>
      <div className="text-2xl font-bold mt-0.5">{count}</div>
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

// ===================== 后台管理微型组件 =====================
function AdminTh({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-5 py-3 text-left text-[11px] font-semibold text-[#8E8E93] uppercase tracking-wider ${className || ""}`}>
      {children}
    </th>
  );
}
function AdminTd({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-5 py-3 text-sm text-[#1C1C1E] ${className || ""}`}>{children}</td>;
}
function AdminKV({ label, value, isWide }: { label: string; value: string; isWide?: boolean }) {
  return (
    <div className={isWide ? "col-span-full" : ""}>
      <span className="text-[#8E8E93]">{label}</span>
      <p className="text-[#1C1C1E] font-medium mt-0.5 break-all">{value}</p>
    </div>
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

/** 后台管理面板 */
function AdminPanel() {
  const [users, setUsers] = useState<Record<string, UserInfo>>({});
  const [uid, setUid] = useState("");
  const [name, setName] = useState("");
  const [pwd, setPwd] = useState("");
  const [role, setRole] = useState("录入员");
  const [resetUid, setResetUid] = useState<string | null>(null);
  const [resetPwd, setResetPwd] = useState("");
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // 订单数据总览
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [taskLoading, setTaskLoading] = useState(false);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  const msgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => { return () => { if (msgTimerRef.current) clearTimeout(msgTimerRef.current); }; }, []);

  const flash = (text: string, type: "success" | "error") => {
    setMsg({ text, type });
    if (msgTimerRef.current) clearTimeout(msgTimerRef.current);
    msgTimerRef.current = setTimeout(() => setMsg(null), 3000);
  };

  const fetchUsers = async () => {
    try {
      const res = await getUsers();
      setUsers(res.users);
    } catch { flash("用户列表加载失败", "error"); }
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
    fetchUsers();
    fetchTasks();
  }, []);

  const handleSave = async () => {
    if (!uid || !name || !pwd) return;
    try {
      await apiCreateUser({ uid, pwd, role, name });
      flash(`成功保存账号: ${uid}`, "success");
      fetchUsers();
      setUid(""); setName(""); setPwd("");
    } catch { flash("保存失败", "error"); }
  };

  const handleDelete = async (u: string) => {
    try {
      await apiDeleteUser(u);
      flash(`已删除账号: ${u}`, "success");
      fetchUsers();
    } catch { flash("删除失败", "error"); }
  };

  const handleResetPassword = async () => {
    if (!resetUid || !resetPwd) return;
    try {
      await apiResetPassword(resetUid, resetPwd);
      flash(`已重置 ${resetUid} 的密码`, "success");
      setResetUid(null);
      setResetPwd("");
    } catch { flash("重置失败", "error"); }
  };

  const roleOptions = [
    { value: "录入员", label: "录入员" },
    { value: "绘图员", label: "绘图员" },
    { value: "初审员", label: "初审员" },
    { value: "总工", label: "总工" },
    { value: "超级管理员", label: "超级管理员" },
  ];

  const statusColor = (s: string) => {
    if (s === "已通过") return "bg-[#E5FBE5] text-[#34C759]";
    if (s === "待修改") return "bg-[#FFE5E5] text-[#FF3B30]";
    if (s.includes("待")) return "bg-[#FFF3E0] text-[#FF9500]";
    return "bg-[#F2F2F7] text-[#8E8E93]";
  };

  return (
    <div>
      <h3 className="text-xl font-semibold text-[#1C1C1E] mb-4">系统后台管理</h3>

      {msg && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
          msg.type === "success" ? "bg-[#E5FBE5] text-[#34C759]" : "bg-[#FFE5E5] text-[#FF3B30]"
        }`}>
          {msg.text}
        </div>
      )}

      {/* ========== 账号管理 ========== */}
      <div className="bg-white rounded-2xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden mb-8">
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
              onClick={handleSave}
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
                <AdminTh>账号</AdminTh>
                <AdminTh>姓名</AdminTh>
                <AdminTh>角色</AdminTh>
                <AdminTh>默认模块</AdminTh>
                <AdminTh>密码</AdminTh>
                <AdminTh className="text-right">操作</AdminTh>
              </tr>
            </thead>
            <tbody>
              {Object.entries(users).map(([uId, info]) => (
                <tr key={uId} className="border-b border-[#F2F2F7] hover:bg-[#FAFAFC] transition-colors">
                  <AdminTd><span className="font-semibold text-[#1C1C1E]">{uId}</span></AdminTd>
                  <AdminTd>{info.name}</AdminTd>
                  <AdminTd>
                    <span className="px-2 py-0.5 rounded-md bg-[#F2F2F7] text-[#1C1C1E] text-xs font-medium">
                      {info.role}
                    </span>
                  </AdminTd>
                  <AdminTd className="text-[#8E8E93]">{info.default_module}</AdminTd>
                  <AdminTd>
                    <span className="font-mono text-[#8E8E93] tracking-wider">
                      {"•".repeat(Math.min(info.password.length, 8))}
                    </span>
                  </AdminTd>
                  <AdminTd>
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => { setResetUid(uId); setResetPwd(""); }}
                        className="px-3 py-1 rounded-md text-xs font-medium text-[#007AFF] hover:bg-[#E8F2FF] transition-all"
                      >
                        重置密码
                      </button>
                      {uId !== "admin" ? (
                        <button
                          onClick={() => handleDelete(uId)}
                          className="px-3 py-1 rounded-md text-xs font-medium text-[#FF3B30] hover:bg-[#FFF0F0] transition-all"
                        >
                          删除
                        </button>
                      ) : (
                        <span className="text-xs text-[#C7C7CC]">内置</span>
                      )}
                    </div>
                  </AdminTd>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 重置密码弹窗 */}
      {resetUid && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-2xl p-6 shadow-2xl max-w-sm w-full mx-4">
            <h4 className="text-lg font-semibold text-[#1C1C1E] mb-4">重置密码: {resetUid}</h4>
            <input
              type="password"
              placeholder="新密码"
              value={resetPwd}
              onChange={(e) => setResetPwd(e.target.value)}
              className="w-full px-3 py-2 mb-4 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none focus:border-[#007AFF]"
              autoFocus
            />
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setResetUid(null); setResetPwd(""); }}
                className="px-4 py-2 rounded-lg bg-[#F2F2F7] text-[#1C1C1E] text-sm font-medium hover:bg-[#E5E5EA] transition-all"
              >
                取消
              </button>
              <button
                onClick={handleResetPassword}
                disabled={!resetPwd}
                className="px-4 py-2 rounded-lg bg-[#007AFF] text-white text-sm font-semibold hover:opacity-90 transition-all disabled:opacity-40"
              >
                确认重置
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== 下拉选项管理 ========== */}
      <DropdownOptionsManager />

      {/* ========== 订单数据总览 ========== */}
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
                <AdminTh>ID</AdminTh>
                <AdminTh>日期</AdminTh>
                <AdminTh>客户</AdminTh>
                <AdminTh>项目</AdminTh>
                <AdminTh>门型</AdminTh>
                <AdminTh>洞口尺寸</AdminTh>
                <AdminTh>制单人</AdminTh>
                <AdminTh>状态</AdminTh>
                <AdminTh className="text-right">详情</AdminTh>
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
                  <React.Fragment key={t.id}>
                    <tr
                      className="border-b border-[#F2F2F7] hover:bg-[#FAFAFC] transition-colors cursor-pointer"
                      onClick={() => setExpandedTask(expandedTask === t.id ? null : t.id)}
                    >
                      <AdminTd><span className="font-mono text-xs text-[#8E8E93]">{t.id}</span></AdminTd>
                      <AdminTd>{t.date}</AdminTd>
                      <AdminTd className="font-medium text-[#1C1C1E]">{t.customer}</AdminTd>
                      <AdminTd className="max-w-[140px] truncate">{t.project}</AdminTd>
                      <AdminTd>{t.door_type}</AdminTd>
                      <AdminTd className="font-mono text-xs">{t.size}</AdminTd>
                      <AdminTd className="text-[#8E8E93]">{t.params?.hhxd || "-"}</AdminTd>
                      <AdminTd>
                        <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium ${statusColor(t.status)}`}>
                          {t.status}
                        </span>
                      </AdminTd>
                      <AdminTd>
                        <div className="flex justify-end">
                          <span className="text-xs text-[#007AFF] font-medium">
                            {expandedTask === t.id ? "收起 ↑" : "展开 ↓"}
                          </span>
                        </div>
                      </AdminTd>
                    </tr>
                    {expandedTask === t.id && (
                      <tr className="bg-[#FAFAFC] border-b border-[#F2F2F7]">
                        <td colSpan={9} className="px-6 py-4">
                          <div className="grid grid-cols-3 md:grid-cols-5 gap-3 text-xs">
                            <AdminKV label="订单号" value={t.params?.ddh || "-"} />
                            <AdminKV label="材质" value={t.params?.zzcl || "-"} />
                            <AdminKV label="颜色" value={t.params?.ys || "-"} />
                            <AdminKV label="开向" value={`${t.params?.sel_kx || ""}${t.params?.sel_nk || ""}`} />
                            <AdminKV label="数量" value={t.params?.sl || "-"} />
                            <AdminKV label="下槛" value={t.params?.threshold_type || "-"} />
                            <AdminKV label="拉手(正)" value={t.params?.zmls || "-"} />
                            <AdminKV label="拉手(反)" value={t.params?.fmls || "-"} />
                            <AdminKV label="合页" value={t.params?.sel_hys || "-"} />
                            <AdminKV label="门扇厚" value={t.params?.mshd ? `${t.params.mshd}mm` : "-"} />
                            <AdminKV label="气窗" value={t.params?.sel_qc || "无"} />
                            <AdminKV label="门楣" value={t.params?.has_mm ? `${t.params.mm_height}mm` : "无"} />
                            <AdminKV label="立柱" value={t.params?.has_pillar ? `有 (${t.params.pillar_width_str})` : "无"} />
                            <AdminKV label="外包套" value={t.params?.has_outer ? `${t.params.trim_front_in}mm` : "无"} />
                            <AdminKV label="内包套" value={t.params?.has_inner ? `${t.params.trim_back_in}mm` : "无"} />
                            <AdminKV label="包装" value={t.params?.sel_bz || "-"} />
                            <AdminKV label="沟通记录" value={t.ref_text || "无"} isWide />
                            <AdminKV label="审核意见" value={t.review_feedback || "无"} isWide />
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
