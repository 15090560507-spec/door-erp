"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useAuth, useModule } from "@/hooks/useAuth";
import {
  getTasks, getTask, createTask, updateTask, deleteTask, copyTask, getTaskOverview,
  generateCad, generateCadPreview, downloadCadBlob, downloadFileFromUrl,
  getUsers, createUser as apiCreateUser, deleteUser as apiDeleteUser,
  resetPassword as apiResetPassword, apiErrorMessage,
} from "@/lib/api";
import {
  createRenderTask,
  extractTaskLineArt,
  getRenderTask,
  lineArtViewToFile,
  listRenderTasks,
  listRenderModelConfigs,
  type RenderTask,
} from "@/lib/renderApi";
import { DEFAULT_FORM_DATA } from "@/lib/types";
import type { TaskItem, DoorFormData, UserInfo, HistoryEntry, TaskOverviewData } from "@/lib/types";
import DoorForm from "@/components/DoorForm";
import TaskCard from "@/components/TaskCard";
import StatusBadge from "@/components/StatusBadge";
import ClipboardUpload from "@/components/ClipboardUpload";
import { Thumbnail } from "@/components/ImageModal";
import { TaskListSkeleton } from "@/components/Skeleton";
import DropdownOptionsManager from "@/components/DropdownOptionsManager";
import ProductionReleaseButton from "@/components/production/ProductionReleaseButton";
import TaskOverviewDashboard from "@/components/TaskOverviewDashboard";
import NoticeDialog from "@/components/door-cad/NoticeDialog";
import { calculateDoorAreas } from "@/lib/doorAreas";
import { localDateCompact } from "@/lib/dateTime";
import { Inbox, RefreshCw } from "lucide-react";
import { registerNavigationGuard, requestAppNavigation } from "@/lib/navigationGuard";

const SIMPLE_PRODUCT_NAMES = ["牌匾", "铝艺栅栏", "雨棚", "其他"];
const LENGTH_PRODUCT_NAMES = ["牌匾", "雨棚", "其他"];
const QUICK_RENDER_PROMPT = "以当前 CAD 线稿为结构和比例的最高约束，结合上传参考图生成真实、清晰的门类产品正面效果图。参考图用于整体款式、颜色和材质，不得改变门扇、门框、门套、玻璃及五金的位置。最终成图不显示 CAD 线稿、尺寸、文字、标注或辅助轮廓。";

function productSummary(params?: DoorFormData) {
  if (!params) return "";
  if (SIMPLE_PRODUCT_NAMES.includes(params.product_name)) {
    const dimensionLabel = LENGTH_PRODUCT_NAMES.includes(params.product_name) ? "宽×长" : "宽×高";
    return `产品: ${params.product_name} | ${dimensionLabel}: ${params.dw}×${params.dh}`;
  }
  const { frameWidth, frameHeight } = calculateDoorAreas(params);
  return `门型: ${params.door_type} | 门框: ${frameWidth}×${frameHeight}`;
}

function cadDownloadFilename(data: Pick<DoorFormData, "dhdw">) {
  const date = localDateCompact();
  const customer = (data.dhdw || "未命名").trim().replace(/[\\/:*?"<>|\s]+/g, "");
  return `${customer || "未命名"}${date}.dxf`;
}

function cadRequestFingerprint(data: DoorFormData) {
  return JSON.stringify(data);
}

function drawingEditSnapshot(data: DoorFormData, refText: string, refImages: string[]) {
  return JSON.stringify({ data, refText, refImages });
}

function base64ImageToFile(value: string, index: number): File {
  const normalized = value.includes(",") ? value.slice(value.indexOf(",") + 1) : value;
  const binary = window.atob(normalized);
  const bytes = new Uint8Array(binary.length);
  for (let offset = 0; offset < binary.length; offset += 1) bytes[offset] = binary.charCodeAt(offset);
  const format = normalized.startsWith("/9j/")
    ? { extension: "jpg", mimeType: "image/jpeg" }
    : normalized.startsWith("UklGR")
      ? { extension: "webp", mimeType: "image/webp" }
      : normalized.startsWith("R0lGOD")
        ? { extension: "gif", mimeType: "image/gif" }
        : { extension: "png", mimeType: "image/png" };
  return new File([bytes], `drawing-reference-${index + 1}.${format.extension}`, {
    type: format.mimeType,
  });
}

export default function DashboardPage() {
  const activeModule = useModule();
  const { user, setModule } = useAuth();
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<TaskItem | null>(null);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [taskLoading, setTaskLoading] = useState(false);
  const [formData, setFormData] = useState<DoorFormData>(DEFAULT_FORM_DATA);
  const [refText, setRefText] = useState("");
  const [refImages, setRefImages] = useState<string[]>([]);
  const [uploadImgB64, setUploadImgB64] = useState<string | null>(null);
  const [reviewFeedback, setReviewFeedback] = useState("");
  const [cadBlob, setCadBlob] = useState<Blob | null>(null);
  const [cadBlobFingerprint, setCadBlobFingerprint] = useState("");
  const [cadLoading, setCadLoading] = useState(false);
  const [cadPreviewSvg, setCadPreviewSvg] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [quickRenderTask, setQuickRenderTask] = useState<RenderTask | null>(null);
  const [quickRenderLoading, setQuickRenderLoading] = useState(false);
  const [quickRenderError, setQuickRenderError] = useState("");
  const [savedEditSnapshot, setSavedEditSnapshot] = useState<string | null>(null);
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false);
  const [unsavedSaving, setUnsavedSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [cadError, setCadError] = useState<{ title: string; message: string; retry: () => void } | null>(null);
  const [saveSuccessOpen, setSaveSuccessOpen] = useState(false);
  const [filterDate, setFilterDate] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterQ, setFilterQ] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [overview, setOverview] = useState<TaskOverviewData | null>(null);
  const PAGE_SIZE = 20;

  // 用 ref 保存当前模块，保持 fetchTasks 引用稳定。
  const moduleRef = useRef(activeModule);

  // 搜索防抖：输入 300ms 后生效
  const searchQRef = useRef(searchQ);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // setTimeout 清理：防止组件卸载后更新状态
  const flashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigationResolverRef = useRef<((allow: boolean) => void) | null>(null);

  const currentEditSnapshot = useMemo(
    () => drawingEditSnapshot(formData, refText, refImages),
    [formData, refImages, refText],
  );
  const hasUnsavedChanges = Boolean(
    activeTaskId && activeTask && savedEditSnapshot && currentEditSnapshot !== savedEditSnapshot,
  );

  useEffect(() => {
    return () => {
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, []);

  useEffect(() => registerNavigationGuard(() => {
    if (!hasUnsavedChanges) return true;
    if (navigationResolverRef.current) return false;
    setUnsavedDialogOpen(true);
    return new Promise<boolean>((resolve) => {
      navigationResolverRef.current = resolve;
    });
  }), [hasUnsavedChanges]);

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    moduleRef.current = activeModule;
  }, [activeModule]);

  useEffect(() => {
    searchQRef.current = searchQ;
  }, [searchQ]);

  const fetchTasks = useCallback(async (date?: string, status?: string, p: number = 0) => {
    setLoading(true);
    const m = moduleRef.current;
    try {
      const params: { status?: string; date?: string; q?: string; limit: number; offset: number } = {
        limit: PAGE_SIZE,
        offset: p * PAGE_SIZE,
      };
      if (status) {
        params.status = status;
      } else if (m === "任务总览") {
        // 任务总览：融合原汇总看板和后台管理，包含全部业务状态。
        params.status = "待绘制,待初审,待终审,待修改,已通过";
      } else if (m === "图纸绘制") {
        // 绘图员需要看到新任务 + 被打回待修改的任务
        params.status = "待绘制,待修改";
      } else if (m === "图纸初审") {
        params.status = "待初审";
      } else if (m === "图纸终审") {
        params.status = "待终审,已通过";
      }
      if (date) params.date = date;
      if (searchQRef.current) params.q = searchQRef.current;
      const res = await getTasks(params);
      setTasks(res.tasks);
      setTotal(res.total);
    } catch (e) {
      setMessage({ text: "任务列表加载失败，请检查网络连接", type: "error" });
      setTimeout(() => setMessage(null), 4000);
    }
    setLoading(false);
  }, []); // 空依赖：fetchTasks 引用稳定

  const fetchStatusCounts = useCallback(async (date?: string) => {
    const statuses = ["待绘制", "待初审", "待终审", "待修改", "已通过"];
    try {
      const results = await Promise.all(
        statuses.map(async (status) => {
          const res = await getTasks({ status, date: date || undefined, limit: 1, offset: 0 });
          return [status, res.total] as const;
        })
      );
      setStatusCounts(Object.fromEntries(results));
    } catch (e) {
      // 统计失败不阻塞任务列表，卡片保留上一次结果。
    }
  }, []);

  const fetchOverview = useCallback(async () => {
    try {
      setOverview(await getTaskOverview());
    } catch {
      // 总览统计失败不阻塞任务处理。
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(0);
      void fetchTasks(filterDate, filterStatus, 0);
      void fetchStatusCounts(filterDate);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchTasks, fetchStatusCounts, filterDate, filterStatus, searchQ, activeModule]);

  useEffect(() => {
    if (activeModule !== "任务总览" && activeModule !== "图纸绘制") return;
    const timer = window.setTimeout(() => void fetchOverview(), 0);
    return () => window.clearTimeout(timer);
  }, [fetchOverview, activeModule]);

  // 切换模块时自动返回任务列表（保留表单数据以便返回继续编辑）
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setActiveTaskId(null);
      setActiveTask(null);
      setTaskLoading(false);
      setRefText("");
      setRefImages([]);
      setUploadImgB64(null);
      setReviewFeedback("");
      setCadBlob(null);
      setCadBlobFingerprint("");
      setCadPreviewSvg(null);
      setQuickRenderTask(null);
      setQuickRenderLoading(false);
      setQuickRenderError("");
      setSavedEditSnapshot(null);
      setMessage(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeModule]);

  useEffect(() => {
    if (!activeTaskId) return;
    let cancelled = false;
    const taskId = activeTaskId;
    const timer = window.setTimeout(() => {
      setActiveTask(null);
      setTaskLoading(true);
      Promise.all([
        getTask(taskId),
        listRenderTasks(1, undefined, taskId).catch(() => [] as RenderTask[]),
      ]).then(([t, renderTasks]) => {
        if (cancelled) return;
        const loadedFormData = t.params ? {
          ...DEFAULT_FORM_DATA,
          ...t.params,
          // 历史任务没有继承标记，必须继续使用原来的独立反面设置。
          back_panel_same_as_front: t.params.back_panel_same_as_front ?? false,
          child_back_same_as_front: t.params.child_back_same_as_front ?? false,
        } : { ...DEFAULT_FORM_DATA };
        const loadedRefText = t.ref_text || "";
        const loadedRefImages = t.ref_images || [];
        setActiveTask(t);
        setFormData(loadedFormData);
        setRefText(loadedRefText);
        setRefImages(loadedRefImages);
        setSavedEditSnapshot(drawingEditSnapshot(loadedFormData, loadedRefText, loadedRefImages));
        setUploadImgB64(t.drawing_img_b64 || null);
        setReviewFeedback(t.review_feedback || "");
        setCadBlob(null);
        setCadBlobFingerprint("");
        setCadPreviewSvg(null);
        const latestRender = renderTasks[0] || null;
        setQuickRenderTask(latestRender);
        setQuickRenderLoading(Boolean(latestRender && ["pending", "running"].includes(latestRender.status)));
        setQuickRenderError("");
      }).finally(() => {
        if (!cancelled) setTaskLoading(false);
      });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeTaskId]);

  const resetTaskView = () => {
    setActiveTaskId(null);
    setActiveTask(null);
    setFormData({ ...DEFAULT_FORM_DATA });
    setRefText("");
    setRefImages([]);
    setUploadImgB64(null);
    setReviewFeedback("");
    setCadBlob(null);
    setCadBlobFingerprint("");
    setCadPreviewSvg(null);
    setQuickRenderTask(null);
    setQuickRenderLoading(false);
    setQuickRenderError("");
    setSavedEditSnapshot(null);
    setMessage(null);
  };

  const backToList = async (force = false) => {
    if (!force && !(await requestAppNavigation())) return;
    resetTaskView();
  };

  const flash = (text: string, type: "success" | "error" | "info") => {
    setMessage({ text, type });
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    flashTimerRef.current = setTimeout(() => setMessage(null), 4000);
  };

  useEffect(() => {
    const taskId = quickRenderTask?.id;
    const status = quickRenderTask?.status;
    if (!taskId || !["pending", "running"].includes(status || "")) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const poll = async () => {
      controller = new AbortController();
      try {
        const task = await getRenderTask(taskId, controller.signal);
        if (stopped) return;
        setQuickRenderTask(task);
        if (task.status === "completed") {
          setQuickRenderLoading(false);
          flash("效果图生成完成", "success");
          return;
        }
        if (task.status === "failed") {
          setQuickRenderLoading(false);
          setQuickRenderError(task.errorMessage || "效果图生成失败");
          return;
        }
        timer = setTimeout(poll, 3000);
      } catch (error) {
        if (stopped || controller.signal.aborted) return;
        setQuickRenderError(apiErrorMessage(error, "读取效果图生成进度失败"));
        timer = setTimeout(poll, 3000);
      }
    };

    timer = setTimeout(poll, 1500);
    return () => {
      stopped = true;
      controller?.abort();
      if (timer) clearTimeout(timer);
    };
  }, [quickRenderTask?.id, quickRenderTask?.status]);

  const showCadError = (title: string, error: unknown, retry: () => void) => {
    setCadError({
      title,
      message: apiErrorMessage(error, "服务器未返回具体错误，请检查后端服务后重试"),
      retry,
    });
  };

  // 搜索输入防抖：300ms 后生效
  const handleSearchChange = (value: string) => {
    setFilterQ(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setPage(0);
      setSearchQ(value);
    }, 300);
  };

  const clearSearch = () => {
    setFilterQ("");
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    setPage(0);
    setSearchQ("");
  };

  // 未报价/已报价、未确认/已确认 切换（录入模块卡片 + 任务总览）
  const toggleTaskQuoteStatus = async (task: TaskItem) => {
    const next = (task.quote_status || "未报价") === "已报价" ? "未报价" : "已报价";
    try {
      const updated = await updateTask(task.id, { quote_status: next });
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, ...updated } : t)));
      flash(`已切换为${next}`, "success");
    } catch {
      flash("报价状态更新失败", "error");
    }
  };

  const validateDoorForm = (data: DoorFormData): string | null => {
    const missing: string[] = [];
    const isSimpleProduct = ["牌匾", "铝艺栅栏", "雨棚", "其他"].includes(data.product_name);
    if (!data.dhdw.trim()) missing.push("订货单位");
    if (!data.sl.trim()) missing.push("数量(樘)");
    if (!data.product_name.trim()) missing.push("产品名称");
    if (!data.ys.trim()) missing.push("颜色");
    if (isSimpleProduct) {
      if (!data.dw || data.dw <= 0) missing.push("宽度");
      if (!data.dh || data.dh <= 0) missing.push("高度");
      return missing.length > 0 ? `请填写以下必填项：${missing.join("、")}` : null;
    }
    if (!data.mshd || Number(data.mshd) <= 0) missing.push("门扇厚度");
    if (!data.sel_kx.trim()) missing.push("左右开向");
    if (!data.sel_nk.trim()) missing.push("内外开向");
    if (!data.zmks.trim()) missing.push("正面款式");
    if (!data.fmks.trim()) missing.push("反面款式");
    if (!data.zmls.trim()) missing.push("正面拉手");
    if (!data.fmls.trim()) missing.push("反面拉手");
    if (!data.st_val.trim()) missing.push("锁体类型");
    if (!data.sel_hys.trim()) missing.push("开启机构");
    if (!data.fingerprint_lock.trim()) missing.push("指纹锁");
    if (data.use_light_size) {
      if (!data.light_w || data.light_w <= 0) missing.push("见光宽(W)");
      if (!data.light_h || data.light_h <= 0) missing.push("见光高(H)");
    } else {
      if (!data.dw || data.dw <= 0) missing.push("门框总宽(W)");
      if (!data.dh || data.dh <= 0) missing.push("门框总高(H)");
    }
    if (data.is_arch_door) {
      if (!data.arch_spring_height || data.arch_spring_height <= 0) missing.push("起弧高度");
      if (data.dh && data.arch_spring_height >= data.dh) missing.push("起弧高度需小于门框总高");
    }
    if (data.has_outer) {
      if (!data.trim_front_in || data.trim_front_in <= 0) missing.push("外包套宽");
      if (!data.trim_style_outer.trim()) missing.push("外包套款式");
    }
    if (data.has_outer_portal) {
      if (!data.outer_portal_pillar_width || data.outer_portal_pillar_width <= 0) missing.push("门柱宽度");
      if (!data.outer_portal_header_height || data.outer_portal_header_height <= 0) missing.push("门头高度");
    }
    if (data.has_outer_landscape) {
      if (!data.outer_landscape_left_width || data.outer_landscape_left_width <= 0) missing.push("左景宽度");
      if (!data.outer_landscape_right_width || data.outer_landscape_right_width <= 0) missing.push("右景宽度");
      if (!data.outer_landscape_top_height || data.outer_landscape_top_height <= 0) missing.push("上景高度");
    }
    if (data.has_inner) {
      if (!data.trim_back_in || data.trim_back_in <= 0) missing.push("内包套宽");
      if (!data.trim_style_inner.trim()) missing.push("内包套款式");
    }
    if (data.threshold_type === "吊脚" && (!Number.isFinite(data.dj_height) || data.dj_height < 0)) {
      missing.push("吊脚高度");
    }
    if (data.is_integrated_door) {
      if (!data.integrated_panel_height || data.integrated_panel_height <= 0) missing.push("封板高度");
      if (!data.integrated_press_top_rail || data.integrated_press_top_rail <= 0) missing.push("封板压框尺寸");
      if (!data.integrated_glass_height || data.integrated_glass_height <= 0) missing.push("上方玻璃高度");
    }
    if (data.handle_size && !/^\s*\d+(\.\d+)?\s*[*xX×]\s*\d+(\.\d+)?\s*$/.test(data.handle_size)) {
      return "拉手尺寸格式请填写为 40*800 或 800*40";
    }
    return missing.length > 0 ? `请填写以下必填项：${missing.join("、")}` : null;
  };

  // ===================== 录入模块 =====================
  const handleSubmitOrder = async () => {
    const validation = validateDoorForm(formData);
    if (validation) {
      setValidationError(validation);
      return;
    }
    setSubmitting(true);
    try {
      await createTask({ params: formData, ref_text: refText, ref_images: refImages });
      setToast({ text: "订单提交成功，已流转至绘图部！", type: "success" });
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setToast(null), 3000);
      setFormData({ ...DEFAULT_FORM_DATA });
      setRefText("");
      setRefImages([]);
      setModule("图纸绘制");
      fetchTasks(filterDate, filterStatus);
      fetchStatusCounts(filterDate);
      fetchOverview();
    } catch { flash("提交失败", "error"); }
    setSubmitting(false);
  };

  const saveCurrentTask = async (showSuccess = true): Promise<boolean> => {
    if (!activeTaskId) return false;
    const validation = validateDoorForm(formData);
    if (validation) {
      setValidationError(validation);
      return false;
    }
    try {
      await updateTask(activeTaskId, { params: formData, ref_text: refText, ref_images: refImages });
      const updated = await getTask(activeTaskId);
      setActiveTask(updated);
      setSavedEditSnapshot(drawingEditSnapshot(formData, refText, refImages));
      if (showSuccess) setSaveSuccessOpen(true);
      fetchTasks(filterDate, filterStatus);
      fetchStatusCounts(filterDate);
      fetchOverview();
      return true;
    } catch {
      flash("保存失败", "error");
      return false;
    }
  };

  const handleSaveEdit = () => {
    void saveCurrentTask(true);
  };

  const finishUnsavedNavigation = (allow: boolean) => {
    const resolve = navigationResolverRef.current;
    navigationResolverRef.current = null;
    setUnsavedDialogOpen(false);
    resolve?.(allow);
  };

  const handleSaveAndLeave = async () => {
    setUnsavedSaving(true);
    const saved = await saveCurrentTask(false);
    setUnsavedSaving(false);
    if (saved) finishUnsavedNavigation(true);
  };

  const handleDiscardAndLeave = () => {
    setSavedEditSnapshot(currentEditSnapshot);
    finishUnsavedNavigation(true);
  };

  const handleQuickCad = async () => {
    const validation = validateDoorForm(formData);
    if (validation) {
      setValidationError(validation);
      return;
    }
    setCadLoading(true);
    setCadError(null);
    try {
      const blob = await generateCad(formData);
      setCadBlob(blob);
      setCadBlobFingerprint(cadRequestFingerprint(formData));
      downloadCadBlob(blob, cadDownloadFilename(formData));
      flash("CAD 生成完成！", "success");
    } catch (error: unknown) {
      showCadError("CAD 生成失败", error, () => void handleQuickCad());
    } finally {
      setCadLoading(false);
    }
  };

  // ===================== 绘制模块 =====================
  const handleGeneratePreview = async () => {
    const validation = validateDoorForm(formData);
    if (validation) {
      setValidationError(validation);
      return;
    }
    setPreviewLoading(true);
    setCadError(null);
    try {
      const svg = await generateCadPreview(formData);
      setCadPreviewSvg(svg);
      flash("CAD 预览已生成", "success");
    } catch (error: unknown) {
      showCadError("CAD 预览生成失败", error, () => void handleGeneratePreview());
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleGenerateCad = async () => {
    const validation = validateDoorForm(formData);
    if (validation) {
      setValidationError(validation);
      return;
    }
    setCadLoading(true);
    setCadError(null);
    try {
      const fingerprint = cadRequestFingerprint(formData);
      const blob = cadBlob && cadBlobFingerprint === fingerprint ? cadBlob : await generateCad(formData);
      if (blob !== cadBlob) {
        setCadBlob(blob);
        setCadBlobFingerprint(fingerprint);
      }
      downloadCadBlob(blob, cadDownloadFilename(formData));
      flash(cadBlob && cadBlobFingerprint === fingerprint ? "已下载预览时缓存的 DXF" : "基准 CAD 底图已生成并下载", "success");
    } catch (error: unknown) {
      showCadError("CAD 生成失败", error, () => void handleGenerateCad());
    } finally {
      setCadLoading(false);
    }
  };

  const handleGenerateEffect = async () => {
    if (!activeTaskId) return;
    const validation = validateDoorForm(formData);
    if (validation) {
      setValidationError(validation);
      return;
    }
    if (!refImages.length) {
      setQuickRenderError("请先在“沟通记录与参考图”中上传至少一张参考图");
      return;
    }
    setQuickRenderLoading(true);
    setQuickRenderError("");
    setQuickRenderTask(null);
    try {
      const updatedTask = await updateTask(activeTaskId, { params: formData, ref_text: refText, ref_images: refImages });
      setActiveTask(updatedTask);
      setSavedEditSnapshot(drawingEditSnapshot(formData, refText, refImages));
      const [extraction, configs] = await Promise.all([
        extractTaskLineArt(activeTaskId),
        listRenderModelConfigs(false),
      ]);
      const config = [...configs]
        .filter((item) => item.enabled && item.hasApiKey)
        .sort((a, b) => String(b.updatedAt || b.createdAt || "").localeCompare(String(a.updatedAt || a.createdAt || "")))[0];
      if (!config) throw new Error("没有可用的效果渲染模型，请先在效果渲染页面配置并启用模型");
      const lineArt = await lineArtViewToFile(extraction.front, `${activeTaskId}-front-line-art.png`);
      const references = refImages.map(base64ImageToFile);
      const task = await createRenderTask({
        modelConfigId: config.id,
        prompt: QUICK_RENDER_PROMPT,
        size: "2k",
        count: 1,
        selectedAssetIds: [],
        lineArt,
        styleReference: null,
        tempAssets: [],
        renderMode: "precise",
        sourceType: "task",
        sourceSide: "front",
        sourceTaskId: activeTaskId,
        referenceBindings: { panel: { assetIds: [] } },
        referenceFiles: { panel: references },
      });
      setQuickRenderTask(task);
      if (task.status === "completed") {
        setQuickRenderLoading(false);
        flash("效果图生成完成", "success");
      }
    } catch (error) {
      setQuickRenderLoading(false);
      setQuickRenderError(apiErrorMessage(error, "效果图生成失败"));
    }
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
        ref_text: refText,
        ref_images: refImages,
      });
      flash("成功流转至初审！", "success");
      void backToList(true);
      fetchTasks(filterDate, filterStatus);
      fetchStatusCounts(filterDate);
      fetchOverview();
    } catch { flash("提交失败", "error"); }
  };

  // ===================== 初审 / 终审模块 =====================
  const handleReject = async (targetStatus: string) => {
    if (!activeTaskId) return;
    try {
      await updateTask(activeTaskId, { status: targetStatus, review_feedback: reviewFeedback });
      flash("已打回修改", "success");
      void backToList(true);
      fetchTasks(filterDate, filterStatus);
      fetchStatusCounts(filterDate);
      fetchOverview();
    } catch { flash("操作失败", "error"); }
  };

  const handleApprove = async () => {
    if (!activeTaskId) return;
    const nextStatus = activeModule === "图纸初审" ? "待终审" : "已通过";
    const msg = activeModule === "图纸初审" ? "初审通过，已转终审" : "终审通过，可下发生产";
    try {
      await updateTask(activeTaskId, { status: nextStatus, review_feedback: msg });
      flash(msg, "success");
      void backToList(true);
      fetchTasks(filterDate, filterStatus);
      fetchStatusCounts(filterDate);
      fetchOverview();
    } catch { flash("操作失败", "error"); }
  };

  const handleDeleteTask = async (task: TaskItem) => {
    if (!window.confirm(`确认删除 ${task.customer || task.id} 的表单吗？删除后不可恢复。`)) return;
    try {
      await deleteTask(task.id);
      flash("表单已删除", "success");
      fetchTasks(filterDate, filterStatus, page);
      fetchStatusCounts(filterDate);
      fetchOverview();
    } catch (error: unknown) {
      const requestError = error as { userMessage?: string };
      flash(requestError.userMessage || "删除失败", "error");
    }
  };

  const handleCopyTask = async (task: TaskItem) => {
    try {
      const copied = await copyTask(task.id);
      flash(`已复制为新任务 ${copied.id}`, "success");
      setActiveTaskId(copied.id);
      fetchTasks(filterDate, filterStatus, page);
      fetchStatusCounts(filterDate);
      fetchOverview();
    } catch (error: unknown) {
      const requestError = error as { userMessage?: string };
      flash(requestError.userMessage || "复制失败", "error");
    }
  };

  const startNewDrawing = () => {
    setActiveTaskId(null);
    setActiveTask(null);
    setFormData({ ...DEFAULT_FORM_DATA });
    setRefText("");
    setRefImages([]);
    setUploadImgB64(null);
    setReviewFeedback("");
    setCadBlob(null);
    setCadBlobFingerprint("");
    setCadPreviewSvg(null);
    setQuickRenderTask(null);
    setQuickRenderLoading(false);
    setQuickRenderError("");
    setModule("图纸信息录入");
  };

  const returnToDrawingList = async () => {
    if (!(await requestAppNavigation())) return;
    resetTaskView();
    setModule("图纸绘制");
  };

  const applyOverviewQuery = (query: string) => {
    setFilterQ(query);
    setSearchQ(query);
    setPage(0);
  };

  // ===================== 通用背景 =====================
  return (
    <div>
      {saveSuccessOpen && (
        <NoticeDialog
          title="保存成功"
          message="修改已保存"
          onConfirm={() => setSaveSuccessOpen(false)}
        />
      )}

      {unsavedDialogOpen && (
        <div className="ui-dialog-backdrop" onClick={() => !unsavedSaving && finishUnsavedNavigation(false)}>
          <div className="ui-dialog max-w-lg" onClick={(event) => event.stopPropagation()}>
            <div className="ui-dialog__header">
              <h3 className="ui-dialog__title">有未保存的图纸修改</h3>
            </div>
            <div className="ui-dialog__body">
              <p className="text-sm leading-6 text-[#3A3A3C]">
                图纸参数、沟通记录或参考图已经修改。保存后再离开，可以避免返回时内容丢失。
              </p>
            </div>
            <div className="ui-dialog__footer">
              <button
                type="button"
                disabled={unsavedSaving}
                onClick={() => finishUnsavedNavigation(false)}
                className="ui-button ui-button--secondary"
              >
                继续编辑
              </button>
              <button
                type="button"
                disabled={unsavedSaving}
                onClick={handleDiscardAndLeave}
                className="ui-button ui-button--secondary text-[#C93531]"
              >
                不保存离开
              </button>
              <button
                type="button"
                disabled={unsavedSaving}
                onClick={() => void handleSaveAndLeave()}
                className="ui-button ui-button--primary"
              >
                {unsavedSaving ? "正在保存..." : "保存并离开"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 居中 Toast 弹窗 — 点击任意处关闭 */}
      {toast && (
        <div className="ui-dialog-backdrop" onClick={() => setToast(null)}>
          <div className="ui-dialog max-w-sm" onClick={(e) => e.stopPropagation()}>
            <div className="ui-dialog__body text-center">
              <p className={`text-[17px] font-semibold ${toast.type === "success" ? "text-[#248A3D]" : "text-[#C93531]"}`}>{toast.text}</p>
            </div>
          </div>
        </div>
      )}

      {/* 必填项校验弹窗 — 点击任意处关闭 */}
      {validationError && (
        <div className="ui-dialog-backdrop" onClick={() => setValidationError(null)}>
          <div className="ui-dialog max-w-sm" onClick={(e) => e.stopPropagation()}>
            <div className="ui-dialog__header"><h3 className="ui-dialog__title">请检查表单</h3></div>
            <div className="ui-dialog__body"><p className="text-sm leading-6 text-[#C93531]">{validationError}</p></div>
          </div>
        </div>
      )}

      {cadError && (
        <div className="ui-dialog-backdrop" onClick={() => setCadError(null)}>
          <div className="ui-dialog" onClick={(event) => event.stopPropagation()}>
            <div className="ui-dialog__header">
              <h3 className="ui-dialog__title">{cadError.title}</h3>
              <button type="button" onClick={() => setCadError(null)} aria-label="关闭 CAD 错误窗口" className="ui-dialog__close">×</button>
            </div>
            <div className="ui-dialog__body">
              <div className="whitespace-pre-wrap break-words bg-[#FFF2F1] px-4 py-3 text-sm leading-6 text-[#C93531]">
              {cadError.message}
              </div>
            </div>
            <div className="ui-dialog__footer">
              <button type="button" onClick={() => setCadError(null)} className="ui-button ui-button--secondary">关闭</button>
              <button type="button" onClick={() => { const retry = cadError.retry; setCadError(null); retry(); }} className="ui-button ui-button--primary"><RefreshCw size={15} />重新尝试</button>
            </div>
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
              onClick={() => void backToList()}
              className="px-4 py-2 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] text-sm font-medium hover:border-[#007AFF] hover:text-[#007AFF] transition-colors"
            >
              ← 返回列表
            </button>
            <h4 className="text-lg font-semibold text-[#1C1C1E] m-0">
              正在处理：{activeTask.customer} - {activeTask.project} <StatusBadge status={activeTask.status} />
            </h4>
            {activeModule !== "图纸绘制" && (
              <button
                onClick={handleSaveEdit}
                className="ui-button ui-button--primary ml-auto"
              >
                保存修改
              </button>
            )}
          </div>

          {/* 客户沟通记录与参考图：任务进入绘制后也允许继续补充/删除 */}
          <details className="mb-4 bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden" open={activeModule === "图纸绘制"}>
            <summary className="px-5 py-3 font-medium text-[#007AFF] cursor-pointer select-none">
              沟通记录与参考图（可修改）
            </summary>
            <div className="px-5 pb-4 space-y-3">
              <textarea
                value={refText}
                onChange={(e) => setRefText(e.target.value)}
                placeholder="补充或修改沟通要求"
                rows={3}
                className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none resize-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)]"
              />
              <ClipboardUpload onImages={setRefImages} images={refImages} />
              {refImages.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {refImages.map((img: string, idx: number) => (
                    <div key={idx} className="relative group">
                      <Thumbnail b64={img} width={150} />
                      <button
                        onClick={() => setRefImages(refImages.filter((_, i) => i !== idx))}
                        className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >x</button>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[12px] text-[#8E8E93]">
                修改后点击{activeModule === "图纸绘制" ? "生成操作栏右侧" : "上方"}“保存修改”。
              </p>
            </div>
          </details>

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
            {activeModule === "图纸绘制" && (
              <>
                <Card title="第 1 步：生成基准 CAD 底图">
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    <button
                      onClick={handleGeneratePreview}
                      disabled={previewLoading || cadLoading}
                      className="min-h-11 rounded-lg bg-[#F2F2F7] px-4 py-2.5 text-sm font-medium text-[#1C1C1E] transition-all hover:bg-[#E5E5EA] disabled:opacity-50"
                    >
                      {previewLoading ? "正在生成预览..." : "预览 DXF"}
                    </button>
                    <button
                      onClick={handleGenerateCad}
                      disabled={cadLoading || previewLoading}
                      className="min-h-11 rounded-lg border border-[#C7C7CC] bg-white px-4 py-2.5 text-sm font-medium text-[#1C1C1E] transition-all hover:border-[#007AFF] hover:text-[#007AFF] disabled:opacity-50"
                    >
                      {cadLoading ? "生成中..." : "生成 DXF"}
                    </button>
                    <button
                      onClick={handleGenerateEffect}
                      disabled={quickRenderLoading}
                      className="min-h-11 rounded-lg bg-[#007AFF] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:opacity-90 disabled:cursor-wait disabled:opacity-50"
                    >
                      {quickRenderLoading ? "效果图生成中..." : "生成效果图"}
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveEdit}
                      className="min-h-11 rounded-lg bg-[#1C1C1E] px-4 py-2.5 text-sm font-semibold text-white transition-all hover:opacity-90"
                    >
                      保存修改
                    </button>
                  </div>
                  {quickRenderError && (
                    <div className="mt-3 rounded-lg border border-[#FF3B30]/25 bg-[#FF3B30]/5 px-3 py-2 text-sm text-[#C93531]">
                      {quickRenderError}
                    </div>
                  )}
                </Card>

                {quickRenderTask && (
                  <Card title="精准效果图">
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm text-[#636366]">
                        状态：{quickRenderTask.status === "completed" ? "已完成" : quickRenderTask.status === "failed" ? "生成失败" : "生成中"}
                      </p>
                      <button
                        type="button"
                        onClick={handleGenerateEffect}
                        disabled={quickRenderLoading}
                        className="rounded-lg border border-[#C7C7CC] bg-white px-3 py-2 text-sm font-medium text-[#1C1C1E] disabled:opacity-50"
                      >
                        重新生成
                      </button>
                    </div>
                    {quickRenderTask.images?.[0]?.src ? (
                      <div className="rounded-lg border border-[#E5E5EA] bg-[#F7F7FA] p-3">
                        <img src={quickRenderTask.images[0].src} alt="快速生成效果图" className="mx-auto max-h-[720px] w-full object-contain" />
                        <button
                          type="button"
                          onClick={() => void downloadFileFromUrl(quickRenderTask.images[0].src, `${activeTaskId || "door"}-效果图.jpg`)}
                          className="mt-3 rounded-lg bg-[#1C1C1E] px-4 py-2 text-sm font-medium text-white"
                        >
                          下载效果图
                        </button>
                      </div>
                    ) : (
                      <div className="flex min-h-40 items-center justify-center rounded-lg bg-[#F7F7FA] text-sm text-[#8E8E93]">
                        {quickRenderTask.status === "failed" ? quickRenderTask.errorMessage || "效果图生成失败" : "正在生成效果图，请稍候..."}
                      </div>
                    )}
                  </Card>
                )}

                <CadPreviewPanel
                  svg={cadPreviewSvg}
                  loading={previewLoading}
                  onRefresh={handleGeneratePreview}
                />

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
            {activeModule === "图纸初审" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-[17px] font-semibold text-[#1C1C1E] mb-3">图纸全屏预览</h4>
                  {activeTask.drawing_img_b64 ? (
                    <Thumbnail b64={activeTask.drawing_img_b64} width={400} />
                  ) : (
                    <p className="text-[#FF9500] text-sm">绘图员未上传深化图。</p>
                  )}
                  {activeTask.ref_images && activeTask.ref_images.length > 0 && (
                    <details className="mt-3">
                      <summary className="text-[#007AFF] text-sm cursor-pointer">查看参考图 ({activeTask.ref_images.length}张)</summary>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {activeTask.ref_images.map((img: string, idx: number) => (
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
                      {productSummary(activeTask.params)}<br />
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
            {activeModule === "图纸终审" && (
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
                      {productSummary(activeTask.params)}<br />
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
                  {activeTask.status === "已通过" && <ProductionReleaseButton taskId={activeTask.id} />}
                </div>
              </div>
            )}
            {activeTask.history && activeTask.history.length > 0 && (
              <details className="mt-6 bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden">
                <summary className="px-5 py-3 font-medium text-[#8E8E93] cursor-pointer select-none">
                  修改记录 ({activeTask.history.length})
                </summary>
                <div className="px-5 pb-4 space-y-3">
                  {[...activeTask.history].reverse().map((h: HistoryEntry, i: number) => (
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
        </div>
      )}

      {/* ---------- 任务列表模式 ---------- */}
      {!activeTaskId && (
        <div>
          {activeModule === "任务总览" && overview && (
            <TaskOverviewDashboard
              data={overview}
              activeStatus={filterStatus}
              onStatus={setFilterStatus}
              onQuery={applyOverviewQuery}
              onCreate={startNewDrawing}
              onRefresh={() => {
                void fetchOverview();
                void fetchTasks(filterDate, filterStatus, page);
                void fetchStatusCounts(filterDate);
              }}
            />
          )}
          {activeModule === "任务总览" && <AdminSettingsPanel />}

          {/* 录入模块 */}
          {activeModule === "图纸信息录入" && (
            <div>
              <div className="mb-4 flex items-center gap-3">
                <button
                  type="button"
                  onClick={returnToDrawingList}
                  className="rounded-lg border border-[#C7C7CC] bg-white px-4 py-2 text-sm font-medium text-[#1C1C1E] transition-colors hover:border-[#007AFF] hover:text-[#007AFF]"
                >
                  ← 返回图纸绘制列表
                </button>
                <h4 className="text-lg font-semibold text-[#1C1C1E]">新建图纸信息</h4>
              </div>
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
                  onClick={() => { setFormData(DEFAULT_FORM_DATA); setRefText(""); setRefImages([]); setCadPreviewSvg(null); }}
                  className="col-span-2 py-3 rounded-lg bg-[#F2F2F7] text-[#8E8E93] font-medium text-sm hover:bg-[#E5E5EA] hover:text-[#1C1C1E] transition-all"
                >
                  清空表单
                </button>
              </div>

              <div className="mt-6">
                <CadPreviewPanel
                  svg={cadPreviewSvg}
                  loading={previewLoading}
                  onRefresh={handleGeneratePreview}
                />
              </div>
            </div>
          )}

          {/* 其他模块任务列表 */}
          {activeModule !== "图纸信息录入" && (
            <div>
              {/* 统计概览卡片 */}
              {activeModule !== "任务总览" && !filterDate && !filterStatus && (
                <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                  {activeModule === "图纸绘制" && (
                    <>
                      <StatCard label="待绘制" count={statusCounts["待绘制"] ?? 0} color="bg-[#E8E8ED] text-[#48484A]" />
                      <StatCard label="待修改" count={statusCounts["待修改"] ?? 0} color="bg-[#FFEBEB] text-[#CC2F2A]" />
                      <StatCard label="今日新增" count={overview?.today_created ?? 0} color="bg-[#E5F9E5] text-[#248A3D]" />
                      <button
                        type="button"
                        onClick={startNewDrawing}
                        className="flex min-h-20 items-center justify-between rounded-lg border border-[#2B2B30] bg-[#2B2B30] px-4 py-3 text-left text-white shadow-sm transition-colors hover:bg-[#3B3B42]"
                      >
                        <span>
                          <span className="block text-xs text-white/75">新建任务</span>
                          <span className="mt-1 block text-sm font-semibold">图纸信息录入</span>
                        </span>
                        <span aria-hidden="true" className="text-xl">→</span>
                      </button>
                    </>
                  )}
                  {activeModule === "图纸初审" && (
                    <>
                      <StatCard label="待初审" count={statusCounts["待初审"] ?? 0} color="bg-[#FFF3E0] text-[#CC7A00]" />
                      <StatCard label="今日提交" count={overview?.today_created ?? 0} color="bg-[#E8E8ED] text-[#48484A]" />
                    </>
                  )}
                  {activeModule === "图纸终审" && (
                    <>
                      <StatCard label="待终审" count={statusCounts["待终审"] ?? 0} color="bg-[#FFF3E0] text-[#CC7A00]" />
                      <StatCard label="已通过" count={statusCounts["已通过"] ?? 0} color="bg-[#E5F9E5] text-[#248A3D]" />
                    </>
                  )}
                </div>
              )}

              {/* 筛选栏 */}
              <div className="ui-toolbar mb-4">
                <label className="text-[13px] font-medium text-[#8E8E93]">筛选:</label>
                <input
                  type="text"
                  value={filterQ}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder="搜索客户/项目/订单号"
                  className="px-3 py-1.5 text-sm w-56 rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none focus:border-[#007AFF]"
                />
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
                {(filterDate || filterStatus || filterQ) && (
                  <button
                    onClick={() => { setFilterDate(""); setFilterStatus(""); clearSearch(); }}
                    className="px-3 py-1.5 text-xs text-[#007AFF] font-medium hover:underline"
                  >
                    清除筛选
                  </button>
                )}
              </div>

              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-semibold text-[#1C1C1E]">
                  {activeModule === "任务总览" && "全部任务"}
                  {activeModule === "图纸绘制" && "待绘制 / 待修改任务"}
                  {activeModule === "图纸初审" && "待初审任务"}
                  {activeModule === "图纸终审" && "待终审 / 已通过任务"}
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
                <div className="flex flex-col items-center py-10 text-center text-[#8E8E93]">
                  <span className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-white text-[#777780] shadow-sm ring-1 ring-[#E4E4E9]">
                    <Inbox size={19} strokeWidth={1.7} />
                  </span>
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
                      onDelete={["任务总览", "图纸绘制", "图纸信息录入"].includes(activeModule) ? handleDeleteTask : undefined}
                      onCopy={activeModule === "图纸绘制" ? handleCopyTask : undefined}
                      onToggleQuoteStatus={toggleTaskQuoteStatus}
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
function StatCard({
  label,
  count,
  color,
  active = false,
  onClick,
}: {
  label: string;
  count: number;
  color: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const className = `min-h-[76px] w-full rounded-xl border p-4 text-left ${color} bg-opacity-15 transition-all ${
    active ? "border-current ring-2 ring-current/20" : "border-transparent"
  } ${onClick ? "cursor-pointer hover:border-current/40" : ""}`;
  const content = (
    <>
      <div className="text-[11px] font-medium opacity-70">{label}</div>
      <div className="text-2xl font-bold mt-0.5">{count}</div>
    </>
  );
  if (!onClick) return <div className={className}>{content}</div>;
  return (
    <button type="button" onClick={onClick} aria-pressed={active} className={className}>
      {content}
    </button>
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

function CadPreviewPanel({
  svg,
  loading,
  onRefresh,
}: {
  svg: string | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const canOpen = Boolean(svg);
  const zoomPercent = Math.round(zoom * 100);

  const openPreview = () => {
    if (!canOpen) return;
    setIsOpen(true);
  };

  const zoomOut = () => setZoom((value) => Math.max(0.5, Number((value - 0.25).toFixed(2))));
  const zoomIn = () => setZoom((value) => Math.min(4, Number((value + 0.25).toFixed(2))));
  const resetZoom = () => setZoom(1);
  return (
    <>
      <Card title="CAD 图纸预览">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <p className="text-xs text-[#8E8E93]">
          网页预览用于快速核对图纸；复杂填充可能简化显示，正式交付请下载 DXF 后使用 AutoCAD 打印。
        </p>
          <div className="flex items-center gap-2">
            <button
              onClick={openPreview}
              disabled={!canOpen}
              className="px-4 py-2 rounded-lg bg-white text-[#1C1C1E] border border-[#C7C7CC] text-sm font-medium hover:border-[#007AFF] hover:text-[#007AFF] transition-all disabled:opacity-40"
            >
              放大查看
            </button>
            <button
              onClick={onRefresh}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-[#007AFF] text-white text-sm font-semibold hover:opacity-90 transition-all disabled:opacity-50"
            >
              {loading ? "生成中..." : "生成预览"}
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={openPreview}
          disabled={!canOpen}
          className="block w-full text-left h-[560px] overflow-auto rounded-lg border border-[#D1D5DB] bg-[#F8FAFC] p-3 disabled:cursor-default"
        >
          {svg ? (
            <div
              className="[&_svg]:block [&_svg]:w-full [&_svg]:h-auto [&_svg]:min-w-[1100px]"
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-sm text-[#8E8E93]">
              点击“生成预览”查看当前图纸。
            </div>
          )}
        </button>
      </Card>

      {isOpen && svg && (
        <div className="fixed inset-0 z-[100] bg-black/70 p-4">
          <div className="h-full rounded-xl bg-white shadow-2xl flex flex-col overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-[#E5E5EA]">
              <div>
                <h3 className="text-base font-semibold text-[#1C1C1E]">CAD 图纸预览</h3>
                <p className="text-xs text-[#8E8E93]">滚动查看全图，使用缩放按钮放大标注文字。</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={zoomOut}
                  className="w-9 h-9 rounded-lg border border-[#C7C7CC] text-lg font-semibold hover:border-[#007AFF] hover:text-[#007AFF]"
                  aria-label="缩小"
                >
                  -
                </button>
                <button
                  onClick={resetZoom}
                  className="min-w-16 h-9 px-3 rounded-lg border border-[#C7C7CC] text-sm font-medium hover:border-[#007AFF] hover:text-[#007AFF]"
                >
                  {zoomPercent}%
                </button>
                <button
                  onClick={zoomIn}
                  className="w-9 h-9 rounded-lg border border-[#C7C7CC] text-lg font-semibold hover:border-[#007AFF] hover:text-[#007AFF]"
                  aria-label="放大"
                >
                  +
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="ml-2 px-4 h-9 rounded-lg bg-[#1C1C1E] text-white text-sm font-semibold hover:opacity-90"
                >
                  关闭
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto bg-[#F8FAFC] p-4">
              <div
                className="[&_svg]:block [&_svg]:w-full [&_svg]:h-auto"
                style={{ width: `${zoom * 100}%`, minWidth: 1200 }}
                dangerouslySetInnerHTML={{ __html: svg }}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ===================== 任务总览管理设置 =====================
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

/** 任务总览中的超级管理员设置 */
function AdminSettingsPanel() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "超级管理员";
  const [users, setUsers] = useState<Record<string, UserInfo>>({});
  const [uid, setUid] = useState("");
  const [name, setName] = useState("");
  const [pwd, setPwd] = useState("");
  const [role, setRole] = useState("录入员");
  const [resetUid, setResetUid] = useState<string | null>(null);
  const [resetPwd, setResetPwd] = useState("");
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const msgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => { return () => { if (msgTimerRef.current) clearTimeout(msgTimerRef.current); }; }, []);

  const flash = (text: string, type: "success" | "error") => {
    setMsg({ text, type });
    if (msgTimerRef.current) clearTimeout(msgTimerRef.current);
    msgTimerRef.current = setTimeout(() => setMsg(null), 3000);
  };

  const fetchUsers = async () => {
    if (!isSuperAdmin) return;
    try {
      const res = await getUsers();
      setUsers(res.users);
    } catch { flash("用户列表加载失败", "error"); }
  };

  useEffect(() => {
    if (!isSuperAdmin) return;
    const timer = window.setTimeout(() => void fetchUsers(), 0);
    return () => window.clearTimeout(timer);
  }, [isSuperAdmin]);

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

  if (!isSuperAdmin) return null;

  return (
    <details className="mb-6 overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
      <summary className="cursor-pointer select-none px-5 py-4 text-[15px] font-semibold text-[#1C1C1E]">
        管理设置（仅超级管理员）
      </summary>
      <div className="border-t border-[#F2F2F7] p-5">

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
      </div>
    </details>
  );
}
