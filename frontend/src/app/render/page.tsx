"use client";

import { ChangeEvent, ClipboardEvent, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import TaskProjectCombobox from "@/components/TaskProjectCombobox";
import { downloadFileFromUrl, getTasks } from "@/lib/api";
import type { TaskItem } from "@/lib/types";
import {
  RENDER_CATEGORIES,
  createRenderModelConfig,
  createRenderSegmentation,
  createRenderTask,
  confirmRenderSegmentation,
  deleteRenderAsset,
  deleteRenderModelConfig,
  deleteRenderTask,
  extractDxfLineArt,
  extractTaskLineArt,
  extractUploadedLineArt,
  generateRenderTaskPsd,
  lineArtViewToFile,
  listRenderAssets,
  listRenderModelConfigs,
  listRenderTasks,
  regenerateRenderComponent,
  updateRenderModelConfig,
  updateLineArtCrop,
  uploadRenderAsset,
  type ModelConfigInput,
  type RenderAsset,
  type RenderModelConfig,
  type RenderTask,
  type LineArtExtraction,
  type RenderMode,
  type RenderReferenceRole,
  type RenderSegmentation,
} from "@/lib/renderApi";

const DEFAULT_PROMPT = "基于图纸生成清晰、真实的门类产品效果图。严格保持门型结构、比例和部件位置，以参考款式图为整体风格参考，配件素材仅用于对应部件、材质、颜色和细节。最终成图不显示 CAD 线稿、尺寸线、文字、标注箭头或辅助轮廓，玻璃和五金位于门扇表面上方，接缝表现为真实窄黑缝。";
const ASSET_PAGE_SIZE = 24;
const TASK_LIST_LIMIT = 20;
const REFERENCE_ROLE_OPTIONS: Array<{ role: RenderReferenceRole; label: string; description: string; required?: boolean }> = [
  { role: "panel", label: "门扇款式", description: "控制门扇内部款式、颜色和质感", required: true },
  { role: "trim", label: "门套 / 门头门柱", description: "控制门套、门头和门柱的造型与材质" },
  { role: "frame", label: "门框材质", description: "为空时继承门扇颜色与材质" },
  { role: "glass", label: "玻璃", description: "控制玻璃颜色、透明度、纹理和反光" },
  { role: "hardware", label: "五金配件", description: "拉手、锁具、合页、花件及其他配件" },
];
const REFERENCE_ROLE_LABEL = Object.fromEntries(REFERENCE_ROLE_OPTIONS.map((item) => [item.role, item.label])) as Record<RenderReferenceRole, string>;

function resolveRenderSize(renderMode: RenderMode, selectedSize: string) {
  if (selectedSize === "auto") return renderMode === "precise" ? "4k" : "2k";
  return selectedSize;
}
const LineArtCropEditor = dynamic(() => import("@/components/LineArtCropEditor"), {
  ssr: false,
  loading: () => <div className="flex min-h-72 items-center justify-center text-sm text-[#8E8E93]">正在加载裁剪工具...</div>,
});
const RenderSegmentationEditor = dynamic(() => import("@/components/RenderSegmentationEditor"), {
  ssr: false,
  loading: () => <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/35 text-sm text-white">正在加载区域校对工具...</div>,
});
const EMPTY_CONFIG: ModelConfigInput = {
  name: "",
  provider: "image2_proxy",
  baseUrl: "",
  apiKey: "",
  model: "image2",
  endpoint: "/images/edits",
  apiType: "openai_images_edits",
  defaultSize: "original",
  timeoutSeconds: 180,
  enabled: true,
};

interface ReferenceGroup {
  id: string;
  role: RenderReferenceRole;
  label: string;
  assetIds: string[];
  files: File[];
}

function createDefaultReferenceGroups(): ReferenceGroup[] {
  return REFERENCE_ROLE_OPTIONS.map(({ role, label }) => ({
    id: `${role}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    label,
    assetIds: [],
    files: [],
  }));
}

function getSelectedReferenceRoles(referenceGroups: ReferenceGroup[]) {
  const roles = new Set<RenderReferenceRole>();
  for (const group of referenceGroups) {
    if (group.files.length || group.assetIds.length) roles.add(group.role);
  }
  return Array.from(roles);
}

function buildReferencePromptGuidance(roles: RenderReferenceRole[]) {
  if (!roles.length) return "";
  const lines = roles.map((role) => `${REFERENCE_ROLE_LABEL[role]}参考图只能作用于${REFERENCE_ROLE_LABEL[role]}区域，不得影响其他部件。`);
  return `本次参考素材使用规则：${lines.join(" ")}线稿的结构、比例、分格和五金位置优先级最高。`;
}

function buildRenderPrompt(prompt: string, guidance: string) {
  const basePrompt = prompt.trim();
  if (!guidance) return basePrompt;
  return `${basePrompt}\n\n${guidance}`;
}

export default function RenderPage() {
  const [configs, setConfigs] = useState<RenderModelConfig[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState("");
  const [configForm, setConfigForm] = useState<ModelConfigInput>(EMPTY_CONFIG);
  const [editingConfigId, setEditingConfigId] = useState("");
  const [assets, setAssets] = useState<RenderAsset[]>([]);
  const [tasks, setTasks] = useState<RenderTask[]>([]);
  const [modelConfigOpen, setModelConfigOpen] = useState(false);
  const [assetLibraryOpen, setAssetLibraryOpen] = useState(false);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [assetOffset, setAssetOffset] = useState(0);
  const [assetHasMore, setAssetHasMore] = useState(false);
  const [assetLoading, setAssetLoading] = useState(false);
  const [lineArt, setLineArt] = useState<File | null>(null);
  const [lineArtSource, setLineArtSource] = useState<"task" | "dxf" | "upload" | "direct">("task");
  const [drawingTasks, setDrawingTasks] = useState<TaskItem[]>([]);
  const [selectedDrawingTaskId, setSelectedDrawingTaskId] = useState("");
  const [orderSheet, setOrderSheet] = useState<File | null>(null);
  const [dxfFile, setDxfFile] = useState<File | null>(null);
  const [lineArtExtraction, setLineArtExtraction] = useState<LineArtExtraction | null>(null);
  const [selectedLineArtSide, setSelectedLineArtSide] = useState<"front" | "back">("front");
  const [lineArtBusy, setLineArtBusy] = useState(false);
  const [cropEditorOpen, setCropEditorOpen] = useState(false);
  const [segmentation, setSegmentation] = useState<RenderSegmentation | null>(null);
  const [segmentationEditorOpen, setSegmentationEditorOpen] = useState(false);
  const [psdConvertPrompt, setPsdConvertPrompt] = useState(false);
  const [referenceGroups, setReferenceGroups] = useState<ReferenceGroup[]>(() => createDefaultReferenceGroups());
  const [activeReferenceRole, setActiveReferenceRole] = useState<RenderReferenceRole>("panel");
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [size, setSize] = useState("auto");
  const [count, setCount] = useState(1);
  const [activeTask, setActiveTask] = useState<RenderTask | null>(null);
  const [message, setMessage] = useState("");
  const [errorDialog, setErrorDialog] = useState<{ title: string; message: string; raw?: string } | null>(null);
  const [previewImage, setPreviewImage] = useState<{ src: string; title: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitConfigText, setSubmitConfigText] = useState("");
  const [submitWatchSince, setSubmitWatchSince] = useState<number | null>(null);
  const selectedConfig = configs.find((item) => item.id === selectedConfigId);
  const selectedReferenceAssetIds = Array.from(new Set(referenceGroups.flatMap((group) => group.assetIds)));
  const selectedReferenceFiles = referenceGroups.flatMap((group) => group.files);
  const selectedReferenceAssetCount = selectedReferenceAssetIds.length;
  const uploadedReferenceFileCount = selectedReferenceFiles.length;
  const activeReferenceGroup = referenceGroups.find((group) => group.role === activeReferenceRole) || referenceGroups[0];
  const selectedReferenceRoles = getSelectedReferenceRoles(referenceGroups);
  const referencePromptGuidance = buildReferencePromptGuidance(selectedReferenceRoles);
  const activeTaskId = activeTask?.id || "";
  const activeTaskStatus = activeTask?.status || "";

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    const initialize = async () => {
      try {
        const [nextConfigs, nextTasks, drawings] = await Promise.all([
          listRenderModelConfigs(true, controller.signal),
          listRenderTasks(TASK_LIST_LIMIT, controller.signal),
          getTasks({ limit: 100, offset: 0 }, controller.signal),
        ]);
        if (cancelled) return;
        setConfigs(nextConfigs);
        setTasks(nextTasks);
        setDrawingTasks(drawings.tasks || []);
        const defaultConfig = pickDefaultConfig(nextConfigs);
        setSelectedConfigId(defaultConfig?.id || "");
        setEditingConfigId(defaultConfig?.id || "");
        if (defaultConfig) setConfigForm(formFromConfig(defaultConfig));
        setActiveTask(nextTasks[0] || null);
      } catch (error) {
        if (cancelled || controller.signal.aborted) return;
        setMessage(`效果渲染数据加载失败：${(error as Error).message || "请检查网络连接"}`);
      }
    };

    void initialize();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  async function refreshAll() {
    const [nextConfigs, nextTasks] = await Promise.all([
      listRenderModelConfigs(true),
      listRenderTasks(TASK_LIST_LIMIT),
    ]);
    setConfigs(nextConfigs);
    setTasks(nextTasks);
    const nextSelectedConfigId = selectedConfigId || pickDefaultConfig(nextConfigs)?.id || "";
    setSelectedConfigId(nextSelectedConfigId);
    const config = nextConfigs.find((item) => item.id === nextSelectedConfigId);
    if (config) {
      setEditingConfigId(config.id);
      setConfigForm(formFromConfig(config));
    }
    setActiveTask((current) => {
      if (!nextTasks.length) return null;
      if (!current) return nextTasks[0];
      const refreshed = nextTasks.find((task) => task.id === current.id);
      if (refreshed) return refreshed;
      return nextTasks[0];
    });
  }

  async function loadAssets(options: { reset?: boolean; categoryValue?: string; searchValue?: string } = {}) {
    const reset = Boolean(options.reset);
    const nextCategory = options.categoryValue ?? category;
    const nextSearch = options.searchValue ?? search;
    const nextOffset = reset ? 0 : assetOffset;
    setAssetLoading(true);
    try {
      const nextAssets = await listRenderAssets({
        category: nextCategory || undefined,
        q: nextSearch || undefined,
        limit: ASSET_PAGE_SIZE,
        offset: nextOffset,
      });
      setAssets((current) => reset ? nextAssets : [...current, ...nextAssets]);
      setAssetOffset(nextOffset + nextAssets.length);
      setAssetHasMore(nextAssets.length === ASSET_PAGE_SIZE);
    } finally {
      setAssetLoading(false);
    }
  }

  async function toggleAssetLibrary() {
    const nextOpen = !assetLibraryOpen;
    setAssetLibraryOpen(nextOpen);
    if (nextOpen && assets.length === 0 && !assetLoading) {
      try {
        await loadAssets({ reset: true });
      } catch (error) {
        setErrorDialog({ title: "素材库加载失败", message: (error as { userMessage?: string; message?: string }).userMessage || (error as Error).message || "请稍后重试" });
      }
    }
  }

  async function handleCategoryChange(value: string) {
    setCategory(value);
    await loadAssets({ reset: true, categoryValue: value });
  }

  async function handleSearchBlur() {
    await loadAssets({ reset: true });
  }

  async function saveConfig(options: { silent?: boolean } = {}): Promise<RenderModelConfig | null> {
    if (!configForm.name.trim() || !configForm.baseUrl.trim() || !configForm.model.trim()) {
      setMessage("请填写配置名称、Base URL 和 Model");
      return null;
    }
    const apiKeyDraft = configForm.apiKey || "";
    const saved = editingConfigId
      ? await updateRenderModelConfig(editingConfigId, configForm)
      : await createRenderModelConfig(configForm);
    const nextConfigs = await listRenderModelConfigs(true);
    setConfigs(nextConfigs);
    setSelectedConfigId(saved.id);
    setEditingConfigId(saved.id);
    setConfigForm({ ...formFromConfig(saved), apiKey: apiKeyDraft });
    if (!options.silent) setMessage(`模型配置已保存：${saved.model}，API Key ${apiKeyDraft || saved.hasApiKey ? "已保存" : "未填写"}`);
    return saved;
  }

  function editConfig(config: RenderModelConfig) {
    setSelectedConfigId(config.id);
    setEditingConfigId(config.id);
    setConfigForm(formFromConfig(config));
  }

  function handleSelectConfig(configId: string) {
    setSelectedConfigId(configId);
    const config = configs.find((item) => item.id === configId);
    if (config) editConfig(config);
  }

  async function removeAsset(assetId: string) {
    await deleteRenderAsset(assetId);
    setAssets((current) => current.filter((item) => item.id !== assetId));
    setReferenceGroups((current) => current.map((group) => ({ ...group, assetIds: group.assetIds.filter((id) => id !== assetId) })));
  }

  function toggleReferenceAsset(asset: RenderAsset) {
    setReferenceGroups((current) => {
      const exists = current.some((group) => group.assetIds.includes(asset.id));
      if (exists) {
        return current.map((group) => ({ ...group, assetIds: group.assetIds.filter((id) => id !== asset.id) }));
      }
      const next = current.length ? [...current] : createDefaultReferenceGroups();
      const index = Math.max(0, next.findIndex((group) => group.role === activeReferenceRole));
      next[index] = { ...next[index], assetIds: [...next[index].assetIds, asset.id] };
      return next;
    });
  }

  function removeReferenceAsset(assetId: string) {
    setReferenceGroups((current) => current.map((group) => ({ ...group, assetIds: group.assetIds.filter((id) => id !== assetId) })));
  }

  function addReferenceFiles(files: File[], role: RenderReferenceRole = activeReferenceRole) {
    if (!files.length) return;
    setReferenceGroups((current) => {
      const next = current.length ? [...current] : createDefaultReferenceGroups();
      const index = Math.max(0, next.findIndex((group) => group.role === role));
      next[index] = { ...next[index], files: [...next[index].files, ...files] };
      return next;
    });
  }

  function removeReferenceFile(targetFile: File) {
    setReferenceGroups((current) => current.map((group) => ({
      ...group,
      files: group.files.filter((file) => file !== targetFile),
    })));
  }

  async function selectedLineArtFile(): Promise<File | null> {
    if (lineArtSource === "direct") return lineArt;
    if (!lineArtExtraction) return null;
    return lineArtViewToFile(
      lineArtExtraction[selectedLineArtSide],
      `${selectedLineArtSide === "front" ? "front" : "back"}-line-art.png`,
    );
  }

  async function submitTask(renderMode: RenderMode, segmentationOverride?: RenderSegmentation) {
    if (lineArtSource === "direct" && !lineArt) return setMessage("请上传线稿图");
    if (lineArtSource === "dxf" && !dxfFile) return setMessage("请上传 DXF 文件");
    if (lineArtSource !== "direct" && !lineArtExtraction) return setMessage("请先生成正面和反面线稿");
    const panelReferences = referenceGroups.find((group) => group.role === "panel");
    if (!panelReferences || (!panelReferences.assetIds.length && !panelReferences.files.length)) return setMessage("请为门扇款式选择或上传至少一张参考图");
    if (!prompt.trim()) return setMessage("请填写提示词");
    let selectedLineArt: File | null = null;
    try {
      selectedLineArt = await selectedLineArtFile();
    } catch (error) {
      setErrorDialog({ title: "线稿读取失败", message: (error as Error).message || "无法读取当前线稿" });
      return;
    }
    if (!selectedLineArt) return setMessage("未选择可用线稿");
    const confirmedSegmentation = segmentationOverride || segmentation;
    if (renderMode === "precise" && !["task", "dxf"].includes(lineArtSource) && !confirmedSegmentation?.confirmed) {
      setLineArtBusy(true);
      setMessage("正在识别门扇、门框、门套和五金区域...");
      try {
        const next = await createRenderSegmentation(selectedLineArt);
        setSegmentation(next);
        setSegmentationEditorOpen(true);
        setMessage("请确认彩色部件区域后继续精准生成");
      } catch (error) {
        setErrorDialog({ title: "部件区域识别失败", message: (error as Error).message || "请检查线稿图片后重试" });
      } finally {
        setLineArtBusy(false);
      }
      return;
    }
    setLoading(true);
    setSubmitConfigText("正在保存当前模型配置...");
    setMessage("正在保存当前模型配置...");
    const submittedAt = Date.now();
    setSubmitWatchSince(submittedAt);
    const taskAssetIds = Array.from(new Set(referenceGroups.flatMap((group) => group.assetIds)));
    const effectiveSize = resolveRenderSize(renderMode, size);
    const referenceBindings = Object.fromEntries(referenceGroups.map((group) => [group.role, { assetIds: group.assetIds }])) as Record<RenderReferenceRole, { assetIds: string[] }>;
    const referenceFiles = Object.fromEntries(referenceGroups.map((group) => [group.role, group.files])) as Record<RenderReferenceRole, File[]>;
    try {
      const saved = await saveConfig({ silent: true });
      if (!saved) {
        setLoading(false);
        return;
      }
      const submitSummary = renderConfigSummary(saved);
      setSubmitConfigText(submitSummary);
      setMessage(`正在提交渲染任务：${submitSummary}`);
      const task = await Promise.race([
        createRenderTask({
          modelConfigId: saved.id,
          prompt: buildRenderPrompt(prompt, referencePromptGuidance),
          size: effectiveSize,
          count: 1,
          selectedAssetIds: taskAssetIds,
          lineArt: selectedLineArt,
          styleReference: null,
          tempAssets: [],
          renderMode,
          sourceType: lineArtSource === "task" ? "task" : lineArtSource === "dxf" ? "dxf" : "image",
          sourceSide: selectedLineArtSide,
          sourceTaskId: lineArtSource === "task" ? selectedDrawingTaskId : "",
          referenceBindings,
          referenceFiles,
          segmentationId: confirmedSegmentation?.id,
          sourceDxf: lineArtSource === "dxf" ? dxfFile : null,
        }),
        wait(8000).then(() => null),
      ]);
      if (!task) {
        const recovered = await recoverRecentTask(submittedAt);
        if (recovered) {
          setActiveTask(recovered);
          setMessage(renderTaskStatusMessage(recovered));
          if (!isLiveRenderStatus(recovered.status)) setSubmitWatchSince(null);
        } else {
          setMessage("任务已提交，后端仍在生成中，请稍后点刷新查看结果");
        }
        return;
      }
      setActiveTask(task);
      setTasks(await listRenderTasks());
      setMessage(task.status === "completed" ? `${renderMode === "precise" ? "精准分区" : "快速 AI"}效果图生成完成` : `任务状态：${task.status}`);
      if (!isLiveRenderStatus(task.status)) setSubmitWatchSince(null);
    } catch (error: unknown) {
      const err = error as { userMessage?: string; message?: string; task?: RenderTask; raw?: string };
      const text = err.userMessage || err.message || "效果渲染失败";
      const recovered = await recoverRecentTask(submittedAt);
      if (recovered && recovered.status !== "failed") {
        setActiveTask(recovered);
        setMessage(renderTaskStatusMessage(recovered));
        if (!isLiveRenderStatus(recovered.status)) setSubmitWatchSince(null);
        return;
      }
      if (err.task) {
        setActiveTask(err.task);
      }
      setSubmitWatchSince(null);
      setMessage(text);
      setErrorDialog({ title: "效果渲染失败", message: text, raw: err.raw || err.task?.upstreamRawError || "" });
    } finally {
      setLoading(false);
    }

    async function recoverRecentTask(sinceMs: number): Promise<RenderTask | null> {
      try {
        const latestTasks = await listRenderTasks(TASK_LIST_LIMIT);
        setTasks(latestTasks);
        return latestTasks.find((item) => {
          const createdAt = new Date(item.createdAt).getTime();
          return Number.isFinite(createdAt) && createdAt >= sinceMs - 5000;
        }) || null;
      } catch {
        return null;
      }
    }
  }

  async function generateTaskLineArt() {
    if (!selectedDrawingTaskId) return setMessage("请先选择图纸项目");
    setLineArtBusy(true);
    setMessage("正在从图纸项目提取正面和反面线稿...");
    try {
      const extraction = await extractTaskLineArt(selectedDrawingTaskId);
      setLineArtExtraction(extraction);
      setSegmentation(null);
      setSelectedLineArtSide("front");
      setMessage("正面和反面线稿已生成，请选择本次要使用的一面");
    } catch (error) {
      setErrorDialog({ title: "线稿生成失败", message: (error as { userMessage?: string; message?: string }).userMessage || (error as Error).message });
    } finally {
      setLineArtBusy(false);
    }
  }

  async function handleOrderSheet(file: File | null) {
    setOrderSheet(file);
    setLineArtExtraction(null);
    setSegmentation(null);
    if (!file) return;
    setLineArtBusy(true);
    setMessage("正在识别订单图中的正面和反面门体...");
    try {
      const extraction = await extractUploadedLineArt(file);
      setLineArtExtraction(extraction);
      setSelectedLineArtSide("front");
      setMessage(extraction.reviewRequired ? "已生成候选线稿，请调整裁剪框后确认" : "已识别正面和反面线稿，请选择本次要使用的一面");
      if (extraction.reviewRequired) setCropEditorOpen(true);
    } catch (error) {
      setErrorDialog({ title: "线稿识别失败", message: (error as { userMessage?: string; message?: string }).userMessage || (error as Error).message });
    } finally {
      setLineArtBusy(false);
    }
  }

  async function handleDxf(file: File | null) {
    setDxfFile(file);
    setLineArtExtraction(null);
    setSegmentation(null);
    if (!file) return;
    setLineArtBusy(true);
    setMessage("正在从 DXF 提取正面和反面结构线稿...");
    try {
      const extraction = await extractDxfLineArt(file);
      setLineArtExtraction(extraction);
      setSelectedLineArtSide("front");
      setMessage("DXF 结构已读取，请选择本次生成的一面");
    } catch (error) {
      setErrorDialog({ title: "DXF 读取失败", message: (error as Error).message || "请检查 DXF 文件" });
    } finally {
      setLineArtBusy(false);
    }
  }

  async function saveLineArtCrop(value: Parameters<typeof updateLineArtCrop>[1]) {
    if (!lineArtExtraction) return;
    const updated = await updateLineArtCrop(lineArtExtraction.id, value);
    setLineArtExtraction(updated);
    setSegmentation(null);
    setCropEditorOpen(false);
    setMessage("正面和反面裁剪已更新");
  }

  useEffect(() => {
    if (!submitWatchSince) return;
    let stopped = false;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    const poll = async () => {
      if (stopped) return;
      if (document.hidden) {
        timer = window.setTimeout(poll, 3000);
        return;
      }
      controller = new AbortController();
      try {
        const nextTasks = await listRenderTasks(TASK_LIST_LIMIT, controller.signal);
        if (stopped) return;
        setTasks(nextTasks);
        const recentTask = findRecentRenderTask(nextTasks, submitWatchSince);
        if (!recentTask) {
          if (Date.now() - submitWatchSince > 10 * 60 * 1000) {
            setSubmitWatchSince(null);
            setMessage("任务提交后暂未找到历史记录，请手动刷新确认");
          }
          return;
        }
        setActiveTask(recentTask);
        setMessage(renderTaskStatusMessage(recentTask));
        if (!isLiveRenderStatus(recentTask.status)) {
          setSubmitWatchSince(null);
        }
      } catch {
        // Submit recovery is best-effort; manual refresh still works.
      } finally {
        controller = null;
        if (!stopped) timer = window.setTimeout(poll, 3000);
      }
    };
    void poll();
    return () => {
      stopped = true;
      controller?.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [submitWatchSince]);

  useEffect(() => {
    if (submitWatchSince || !activeTaskId || !isLiveRenderStatus(activeTaskStatus)) return;
    let stopped = false;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    const poll = async () => {
      if (stopped) return;
      if (document.hidden) {
        timer = window.setTimeout(poll, 3000);
        return;
      }
      controller = new AbortController();
      try {
        const nextTasks = await listRenderTasks(TASK_LIST_LIMIT, controller.signal);
        if (stopped) return;
        setTasks(nextTasks);
        const refreshed = nextTasks.find((task) => task.id === activeTaskId);
        if (refreshed) {
          setActiveTask(refreshed);
          if (!isLiveRenderStatus(refreshed.status)) {
            setMessage(renderTaskStatusMessage(refreshed));
          }
        }
      } catch {
        // Polling is best-effort; manual refresh still works.
      } finally {
        controller = null;
        if (!stopped) timer = window.setTimeout(poll, 3000);
      }
    };
    timer = window.setTimeout(poll, 3000);
    return () => {
      stopped = true;
      controller?.abort();
      if (timer) window.clearTimeout(timer);
    };
  }, [activeTaskId, activeTaskStatus, submitWatchSince]);

  async function removeConfig(configId: string) {
    await deleteRenderModelConfig(configId);
    const nextConfigs = await listRenderModelConfigs(true);
    setConfigs(nextConfigs);
    if (selectedConfigId === configId || editingConfigId === configId) {
      const nextConfig = pickDefaultConfig(nextConfigs);
      setSelectedConfigId(nextConfig?.id || "");
      setEditingConfigId(nextConfig?.id || "");
      setConfigForm(nextConfig ? formFromConfig(nextConfig) : EMPTY_CONFIG);
    }
    setMessage("模型配置已停用");
  }

  async function removeTask(taskId: string) {
    try {
      await deleteRenderTask(taskId);
      const nextTasks = await listRenderTasks(TASK_LIST_LIMIT);
      setTasks(nextTasks);
      setActiveTask((current) => current?.id === taskId ? (nextTasks[0] || null) : current);
      setMessage("历史记录已删除");
    } catch (error: unknown) {
      const err = error as { userMessage?: string; message?: string };
      setMessage(err.userMessage || err.message || "历史记录删除失败");
    }
  }

  async function regenerateComponent(role: RenderReferenceRole) {
    if (!activeTask) return;
    try {
      const next = await regenerateRenderComponent(activeTask.id, role);
      setActiveTask(next);
      setMessage(`${REFERENCE_ROLE_LABEL[role]}正在重新生成，其他部件保持不变`);
    } catch (error) {
      setErrorDialog({ title: "部件重新生成失败", message: (error as Error).message || "请稍后重试" });
    }
  }

  async function generatePsd() {
    if (!activeTask) return;
    if (activeTask.renderMode !== "precise") {
      setPsdConvertPrompt(true);
      return;
    }
    try {
      setMessage("正在将透明部件层打包为 PSD...");
      const next = await generateRenderTaskPsd(activeTask.id);
      setActiveTask(next);
      setTasks((current) => current.map((item) => item.id === next.id ? next : item));
      setMessage("分层 PSD 已生成");
    } catch (error) {
      setErrorDialog({ title: "PSD 生成失败", message: (error as Error).message || "请稍后重试" });
    }
  }

  async function downloadPsd() {
    if (!activeTask?.psdFile?.url) return;
    try {
      await downloadFileFromUrl(activeTask.psdFile.url, activeTask.psdFile.originalName || `${activeTask.id}-分层效果图.psd`);
    } catch (error) {
      setErrorDialog({ title: "PSD 下载失败", message: (error as Error).message || "请稍后重试" });
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[18px] font-semibold text-[#1C1C1E]">效果渲染</h1>
          <p className="mt-1 text-[12px] text-[#8E8E93]">线稿图、参考款式图、素材库配件和模型配置全部通过后端统一管理。</p>
        </div>
        {message && <span className="max-w-[520px] rounded-full bg-[#007AFF]/10 px-3 py-1 text-[12px] font-medium text-[#007AFF]">{message}</span>}
      </header>
      {errorDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4">
          <div className="w-full max-w-xl rounded-2xl bg-white p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-[#1C1C1E]">{errorDialog.title}</h2>
              <button type="button" onClick={() => setErrorDialog(null)} className="rounded-lg px-2 py-1 text-[18px] text-[#8E8E93] hover:bg-[#F2F2F7]">×</button>
            </div>
            <p className="rounded-xl bg-[#FF3B30]/10 px-3 py-2 text-[13px] leading-6 text-[#FF3B30]">{errorDialog.message}</p>
            {errorDialog.raw && (
              <details className="mt-3">
                <summary className="cursor-pointer text-[12px] font-medium text-[#007AFF]">查看上游原始返回</summary>
                <pre className="mt-2 max-h-52 overflow-auto rounded-xl bg-[#1C1C1E] p-3 text-[11px] leading-5 text-white">{errorDialog.raw}</pre>
              </details>
            )}
            <div className="mt-4 flex justify-end">
              <button type="button" onClick={() => setErrorDialog(null)} className="rounded-lg bg-[#007AFF] px-4 py-2 text-[13px] font-medium text-white">知道了</button>
            </div>
          </div>
        </div>
      )}
      {psdConvertPrompt && (
        <div className="fixed inset-0 z-[65] flex items-center justify-center bg-black/35 px-4 backdrop-blur-[2px]">
          <div className="w-full max-w-md rounded-2xl border border-white/60 bg-white p-5 shadow-2xl">
            <h2 className="text-[16px] font-semibold text-[#1C1C1E]">需要先生成精准分区结果</h2>
            <p className="mt-2 text-[13px] leading-6 text-[#636366]">快速 AI 图片没有可靠的独立部件层。系统将沿用当前线稿和参考素材转为精准分区生成，完成后即可生成 PSD。</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setPsdConvertPrompt(false)} className="rounded-lg border border-[#D1D1D6] px-4 py-2 text-[13px] font-medium text-[#3C3C43]">取消</button>
              <button type="button" onClick={() => { setPsdConvertPrompt(false); void submitTask("precise"); }} className="rounded-lg bg-[#007AFF] px-4 py-2 text-[13px] font-medium text-white">转为精准生成</button>
            </div>
          </div>
        </div>
      )}
      {previewImage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-5" onClick={() => setPreviewImage(null)}>
          <div className="relative max-h-full max-w-[92vw]" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              onClick={() => setPreviewImage(null)}
              className="absolute -right-3 -top-3 z-10 h-8 w-8 rounded-full bg-white text-[18px] leading-8 text-[#1C1C1E] shadow"
              aria-label="关闭预览"
            >
              ×
            </button>
            <img src={previewImage.src} alt={previewImage.title} className="max-h-[88vh] max-w-full rounded-xl bg-white object-contain shadow-2xl" />
          </div>
        </div>
      )}
      {cropEditorOpen && lineArtExtraction?.sourceUrl && (
        <LineArtCropEditor extraction={lineArtExtraction} onCancel={() => setCropEditorOpen(false)} onSave={saveLineArtCrop} />
      )}
      {segmentationEditorOpen && segmentation && (
        <RenderSegmentationEditor
          segmentation={segmentation}
          onCancel={() => setSegmentationEditorOpen(false)}
          onConfirm={async (masks) => {
            try {
              const confirmed = await confirmRenderSegmentation(segmentation.id, masks);
              setSegmentation(confirmed);
              setSegmentationEditorOpen(false);
              setMessage("部件区域已确认，正在提交精准分区生成...");
              await submitTask("precise", confirmed);
            } catch (error) {
              setErrorDialog({ title: "部件区域保存失败", message: (error as Error).message || "请稍后重试" });
            }
          }}
        />
      )}
      {loading && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-white/65 px-4 backdrop-blur-[2px]">
          <div className="relative w-full max-w-md rounded-2xl border border-[#E5E5EA] bg-white p-5 text-center shadow-xl">
            <button
              type="button"
              onClick={() => {
                setLoading(false);
                setMessage("任务已提交，后台生成中，完成后会自动刷新结果");
              }}
              className="absolute right-3 top-3 h-7 w-7 rounded-full text-[18px] leading-7 text-[#8E8E93] hover:bg-[#F2F2F7]"
              aria-label="关闭提交提示"
            >
              ×
            </button>
            <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-[#007AFF] border-t-transparent" />
            <h2 className="text-[16px] font-semibold text-[#1C1C1E]">正在提交渲染任务</h2>
            <p className="mt-2 text-[12px] leading-5 text-[#8E8E93]">{submitConfigText || "正在保存模型配置并上传图片..."}</p>
          </div>
        </div>
      )}

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <button type="button" onClick={() => setModelConfigOpen((value) => !value)} className="text-left">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{modelConfigOpen ? "▼" : "▶"} 模型配置</h2>
            {selectedConfig && <p className="mt-1 text-[12px] text-[#8E8E93]">当前：{selectedConfig.provider} / {selectedConfig.apiType} / {selectedConfig.model} / {selectedConfig.baseUrl || "未填写 Base URL"} / API Key {selectedConfig.hasApiKey ? "已保存" : "未保存"}</p>}
          </button>
          <div className="flex items-center gap-2">
            <select value={selectedConfigId} onChange={(event) => handleSelectConfig(event.target.value)} className="rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[13px]">
              <option value="">选择模型配置</option>
              {configs.filter((item) => item.enabled).map((config) => <option key={config.id} value={config.id}>{config.name}</option>)}
            </select>
            <button type="button" onClick={() => void saveConfig()} className="rounded-lg bg-[#007AFF] px-3 py-2 text-[13px] font-medium text-white">保存配置</button>
          </div>
        </div>
        {modelConfigOpen && <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          <Input label="配置名称" value={configForm.name} onChange={(value) => setConfigForm({ ...configForm, name: value })} />
          <Select label="Provider" value={configForm.provider} onChange={(value) => setConfigForm({ ...configForm, provider: value })} options={[["image2_proxy", "Image2 中转站"], ["openai_compatible", "OpenAI 兼容"], ["volcengine_ark", "火山方舟"]]} />
          <Input label="Base URL" value={configForm.baseUrl} onChange={(value) => setConfigForm({ ...configForm, baseUrl: value })} />
          <Input label="API Key" type="password" value={configForm.apiKey || ""} onChange={(value) => setConfigForm({ ...configForm, apiKey: value })} placeholder={editingConfigId && selectedConfig?.hasApiKey ? "API Key 已保存，留空则不修改" : ""} />
          <Input label="Model" value={configForm.model} onChange={(value) => setConfigForm({ ...configForm, model: value })} />
          <Input label="Endpoint" value={configForm.endpoint} onChange={(value) => setConfigForm({ ...configForm, endpoint: value })} />
          <Select label="API Type" value={configForm.apiType} onChange={(value) => setConfigForm({ ...configForm, apiType: value })} options={[["openai_images_edits", "OpenAI Images Edits"], ["openai_images_generations", "OpenAI Images Generations"], ["ark_images_generations", "Ark Images Generations"]]} />
          <div className="flex items-end gap-2">
            <button type="button" onClick={() => void saveConfig()} className="h-9 flex-1 rounded-lg bg-[#007AFF] px-3 text-[13px] font-medium text-white">{editingConfigId ? "保存配置" : "新增配置"}</button>
            {editingConfigId && <button type="button" onClick={() => { setEditingConfigId(""); setConfigForm(EMPTY_CONFIG); }} className="h-9 rounded-lg bg-[#F2F2F7] px-3 text-[13px]">取消</button>}
          </div>
        </div>}
        {modelConfigOpen && <div className="mt-3 flex flex-wrap gap-2">
          {configs.map((config) => (
            <span key={config.id} className="inline-flex items-center gap-1 rounded-full bg-[#F2F2F7] px-2 py-1 text-[12px] text-[#3C3C43]">
              <button type="button" onClick={() => editConfig(config)} className="max-w-[260px] truncate">
                {config.name || "未命名"} / {config.baseUrl || "未填 Base URL"} / {config.endpoint || ""} / {config.model || ""}{config.enabled ? "" : "（停用）"}
              </button>
              {config.enabled && <button type="button" onClick={() => removeConfig(config.id)} className="rounded-full px-1 text-[#FF3B30] hover:bg-white">停用</button>}
            </span>
          ))}
        </div>}
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="mr-2">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">线稿来源 *</h2>
            <p className="mt-1 text-[12px] text-[#8E8E93]">生成两张独立线稿后，选择正面或反面作为本次输入。</p>
          </div>
          <div className="flex-1" />
          {(["task", "dxf", "upload", "direct"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => { setLineArtSource(value); setLineArtExtraction(null); setSegmentation(null); }}
              className={`rounded-lg px-3 py-2 text-[12px] font-medium ${lineArtSource === value ? "bg-[#007AFF] text-white" : "bg-[#F2F2F7] text-[#3C3C43]"}`}
            >
              {value === "task" ? "关联图纸项目" : value === "dxf" ? "上传 DXF" : value === "upload" ? "上传完整订单图" : "直接上传线稿"}
            </button>
          ))}
        </div>

        {lineArtSource === "task" && (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]">
            <div>
              <span className="text-[12px] font-medium text-[#8E8E93]">选择图纸项目</span>
              <TaskProjectCombobox tasks={drawingTasks} value={selectedDrawingTaskId} onChange={(value) => { setSelectedDrawingTaskId(value); setLineArtExtraction(null); setSegmentation(null); }} />
            </div>
            <button type="button" onClick={() => void generateTaskLineArt()} disabled={lineArtBusy || !selectedDrawingTaskId} className="self-end rounded-lg bg-[#007AFF] px-4 py-2 text-[13px] font-medium text-white disabled:opacity-50">{lineArtBusy ? "生成中..." : "生成正反面线稿"}</button>
          </div>
        )}

        {lineArtSource === "upload" && (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]">
            <CompactSourceUpload file={orderSheet} onPick={(file) => void handleOrderSheet(file)} />
            {lineArtExtraction?.sourceUrl && <button type="button" onClick={() => setCropEditorOpen(true)} className="self-end rounded-lg bg-[#F2F2F7] px-4 py-2 text-[13px] font-medium">调整裁剪</button>}
          </div>
        )}

        {lineArtSource === "dxf" && (
          <CompactDxfUpload file={dxfFile} busy={lineArtBusy} onPick={(file) => void handleDxf(file)} />
        )}

        {lineArtSource === "direct" && (
          <UploadBox title="线稿图" file={lineArt} onPick={(file) => { setLineArt(file); setSegmentation(null); }} onPreview={(src, title) => setPreviewImage({ src, title })} required />
        )}

        {lineArtSource !== "direct" && lineArtExtraction && (
          <div className="mt-4">
            {lineArtExtraction.warnings?.map((warning) => <p key={warning} className="mb-2 rounded-lg bg-[#FF9500]/10 px-3 py-2 text-[12px] text-[#9A5A00]">{warning}</p>)}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {(["front", "back"] as const).map((side) => (
                <label key={side} className={`cursor-pointer rounded-xl border p-3 ${selectedLineArtSide === side ? "border-[#007AFF] bg-[#007AFF]/5" : "border-[#E5E5EA]"}`}>
                  <div className="mb-2 flex items-center gap-2">
                    <input type="radio" name="line-art-side" checked={selectedLineArtSide === side} onChange={() => setSelectedLineArtSide(side)} />
                    <span className="text-[13px] font-semibold">{side === "front" ? "正面线稿" : "反面线稿"}</span>
                    {selectedLineArtSide === side && <span className="rounded-full bg-[#007AFF] px-2 py-0.5 text-[11px] text-white">本次使用</span>}
                  </div>
                  <button type="button" onClick={(event) => { event.preventDefault(); setPreviewImage({ src: lineArtExtraction[side].url, title: side === "front" ? "正面线稿" : "反面线稿" }); }} className="block w-full rounded-lg bg-white">
                    <img src={lineArtExtraction[side].url} alt={side === "front" ? "正面线稿" : "反面线稿"} className="mx-auto max-h-[360px] w-full object-contain" />
                  </button>
                </label>
              ))}
            </div>
          </div>
        )}
        {["upload", "direct"].includes(lineArtSource) && segmentation && (
          <div className="mt-3 flex items-center gap-3 rounded-xl border border-[#E5E5EA] bg-[#F7F7FA] px-3 py-2">
            <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${segmentation.confirmed ? "bg-[#34C759]/12 text-[#248A3D]" : "bg-[#FF9500]/12 text-[#9A5A00]"}`}>
              {segmentation.confirmed ? "部件区域已确认" : `识别置信度 ${Math.round(segmentation.confidence * 100)}%`}
            </span>
            <span className="flex-1 text-[11px] text-[#8E8E93]">精准模式将严格沿用当前区域边界。</span>
            <button type="button" onClick={() => setSegmentationEditorOpen(true)} className="rounded-lg border border-[#D1D1D6] bg-white px-3 py-1.5 text-[12px] font-medium text-[#3C3C43]">检查区域</button>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E]">部件参考</h2>
          <p className="mt-1 text-[12px] text-[#8E8E93]">先选择作用部件，再从素材库选择或上传参考图；系统不会把门扇、门套和五金素材混用。</p>
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
          {REFERENCE_ROLE_OPTIONS.map((item) => {
            const group = referenceGroups.find((candidate) => candidate.role === item.role);
            const amount = (group?.assetIds.length || 0) + (group?.files.length || 0);
            const active = activeReferenceRole === item.role;
            return (
              <button
                key={item.role}
                type="button"
                onClick={() => setActiveReferenceRole(item.role)}
                className={`min-h-24 rounded-xl border p-3 text-left transition-colors ${active ? "border-[#007AFF] bg-[#007AFF]/5" : "border-[#E5E5EA] bg-[#F7F7FA] hover:bg-white"}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-[#1C1C1E]">{item.label}{item.required ? " *" : ""}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] ${amount ? "bg-[#34C759]/12 text-[#248A3D]" : "bg-white text-[#8E8E93]"}`}>{amount}</span>
                </span>
                <span className="mt-2 block text-[11px] leading-5 text-[#8E8E93]">{item.description}</span>
              </button>
            );
          })}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-[#E5E5EA] bg-[#F7F7FA] p-3">
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold text-[#1C1C1E]">当前作用于：{REFERENCE_ROLE_LABEL[activeReferenceRole]}</p>
            <p className="mt-1 text-[11px] text-[#8E8E93]">在下方素材库点“选择”的图片也会归入当前部件。</p>
          </div>
          <CompactImageUpload files={activeReferenceGroup?.files || []} onChange={(files) => addReferenceFiles(files, activeReferenceRole)} />
        </div>
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => void toggleAssetLibrary()} className="text-left">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{assetLibraryOpen ? "▼" : "▶"} 素材库</h2>
            <p className="mt-1 text-[12px] text-[#8E8E93]">从个人素材库选择，或上传本次专用参考图；选中的内容会统一放到下方本次素材栏。</p>
          </button>
          <div className="flex-1" />
          {assetLibraryOpen && (
            <>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onBlur={handleSearchBlur}
                placeholder="搜索素材"
                className="h-9 rounded-lg border border-[#E5E5EA] px-3 text-[13px]"
              />
              <LibraryUploadButton
                category={category}
                onUploaded={(asset) => {
                  setAssets((current) => [asset, ...current]);
                  setMessage("素材已上传到个人素材库");
                }}
              />
            </>
          )}
        </div>

        {assetLibraryOpen && (
          <>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[132px_1fr]">
              <div className="rounded-xl border border-[#E5E5EA] bg-[#F7F7FA] p-2">
                <button
                  type="button"
                  onClick={() => void handleCategoryChange("")}
                  className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-[12px] font-medium ${category === "" ? "bg-[#007AFF] text-white" : "text-[#3C3C43] hover:bg-white"}`}
                >
                  全部分类
                </button>
                {RENDER_CATEGORIES.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => void handleCategoryChange(item)}
                    className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-[12px] font-medium ${category === item ? "bg-[#007AFF] text-white" : "text-[#3C3C43] hover:bg-white"}`}
                  >
                    {item}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {assets.map((asset) => {
                  const selected = selectedReferenceAssetIds.includes(asset.id);
                  return (
                    <div key={asset.id} className={`grid grid-cols-[120px_1fr] gap-3 rounded-xl border p-2 ${selected ? "border-[#007AFF] bg-[#007AFF]/5" : "border-[#E5E5EA]"}`}>
                      <button
                        type="button"
                        onClick={() => setPreviewImage({ src: asset.url || asset.thumbnailUrl, title: asset.name })}
                        className="aspect-square rounded-lg bg-[#F2F2F7]"
                      >
                        <img src={asset.thumbnailUrl || asset.url} alt={asset.name} loading="lazy" decoding="async" className="h-full w-full object-contain" />
                      </button>
                      <div className="min-w-0">
                        <p className="truncate text-left text-[13px] font-medium text-[#1C1C1E]">{asset.name}</p>
                        <p className="mt-1 truncate text-left text-[12px] text-[#8E8E93]">{asset.category}</p>
                        <div className="mt-4 flex gap-2">
                          <button
                            type="button"
                            onClick={() => toggleReferenceAsset(asset)}
                            className={`flex-1 rounded-lg px-2 py-1.5 text-[12px] font-medium ${selected ? "bg-[#007AFF] text-white" : "bg-[#F2F2F7] text-[#1C1C1E]"}`}
                          >
                            {selected ? "已选" : `用于${REFERENCE_ROLE_LABEL[activeReferenceRole]}`}
                          </button>
                          <button type="button" onClick={() => removeAsset(asset.id)} className="rounded-lg bg-[#F2F2F7] px-3 py-1.5 text-[12px] text-[#FF3B30]">删除</button>
                        </div>
                      </div>
                    </div>
                  );
                })}
                {assetLoading && <p className="col-span-full text-[13px] text-[#8E8E93]">素材加载中...</p>}
                {!assetLoading && !assets.length && <p className="col-span-full text-[13px] text-[#8E8E93]">暂无素材</p>}
              </div>
            </div>

            {assetHasMore && (
              <div className="mt-3 flex justify-center">
                <button type="button" onClick={() => void loadAssets()} disabled={assetLoading} className="rounded-lg bg-[#F2F2F7] px-4 py-2 text-[12px] font-medium text-[#1C1C1E] disabled:opacity-50">
                  {assetLoading ? "加载中..." : "加载更多素材"}
                </button>
              </div>
            )}
          </>
        )}

        <div className="mt-3 rounded-xl border border-[#E5E5EA] bg-[#F7F7FA] p-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <div className="text-[13px] font-semibold text-[#1C1C1E]">本次素材</div>
            <span className="text-[12px] text-[#8E8E93]">已选素材 {selectedReferenceAssetCount} 个，本次上传参考图 {uploadedReferenceFileCount} 个</span>
          </div>
          {(selectedReferenceAssetIds.length > 0 || selectedReferenceFiles.length > 0) ? (
            <div className="flex flex-wrap gap-2">
              {selectedReferenceAssetIds.map((assetId) => {
                const asset = assets.find((item) => item.id === assetId);
                const role = referenceGroups.find((group) => group.assetIds.includes(assetId))?.role;
                return (
                  <span key={assetId} className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-1 text-[11px] text-[#3C3C43]">
                    <button
                      type="button"
                      onClick={() => asset && setPreviewImage({ src: asset.url || asset.thumbnailUrl, title: asset.name })}
                      className="max-w-[180px] truncate"
                    >
                      {role ? `${REFERENCE_ROLE_LABEL[role]}：` : ""}{asset?.name || assetId}
                    </button>
                    <button type="button" onClick={() => removeReferenceAsset(assetId)} className="text-[#FF3B30]">×</button>
                  </span>
                );
              })}
              {referenceGroups.flatMap((group) => group.files.map((file, index) => (
                  <span key={`${group.role}-${file.name}-${file.lastModified}-${index}`} className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-1 text-[11px] text-[#3C3C43]">
                    <span className="text-[#8E8E93]">{REFERENCE_ROLE_LABEL[group.role]}：</span>
                    <TempFileChip file={file} onPreview={(src, title) => setPreviewImage({ src, title })} onRemove={() => removeReferenceFile(file)} />
                  </span>
                ))) }
            </div>
          ) : (
            <p className="text-[12px] text-[#8E8E93]">还没有选择素材。可以在上方素材库点“选择”，或用“上传图”添加本次专用参考图。</p>
          )}
          {referencePromptGuidance && (
            <p className="mt-2 rounded-lg bg-white px-3 py-2 text-[12px] leading-5 text-[#3C3C43]">{referencePromptGuidance}</p>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_160px_120px]">
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">提示词</span>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" />
          </label>
          <Select label="输出清晰度" value={size} onChange={setSize} options={[["auto", "自动（快速 2K / 精准 4K）"], ["1k", "1K"], ["2k", "2K"], ["4k", "4K"]]} />
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">数量</span>
            <input type="number" min={1} max={1} value={count} disabled onChange={(event) => setCount(clampCount(event.target.value))} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px] disabled:bg-[#F2F2F7]" />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="text-[12px] text-[#8E8E93]">已选素材 {selectedReferenceAssetCount} 个，本次上传参考图 {uploadedReferenceFileCount} 个</span>
          <div className="flex-1" />
          <button type="button" onClick={() => void submitTask("quick")} disabled={loading} className="rounded-lg border border-[#D1D1D6] bg-white px-5 py-2 text-[13px] font-medium text-[#1C1C1E] disabled:opacity-50">
            {loading ? "提交中..." : `快速 AI 生成 · ${resolveRenderSize("quick", size).toUpperCase()}`}
          </button>
          <button type="button" onClick={() => void submitTask("precise")} disabled={loading} className="rounded-lg bg-[#007AFF] px-5 py-2 text-[13px] font-medium text-white disabled:opacity-50">
            {loading ? "提交中..." : `精准分区生成 · ${resolveRenderSize("precise", size).toUpperCase()}`}
          </button>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <div className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">生成结果</h2>
            <button type="button" onClick={() => refreshAll()} className="rounded-lg bg-[#F2F2F7] px-3 py-1.5 text-[12px]">刷新</button>
          </div>
          {activeTask?.status === "failed" && activeTask.errorType !== "dxf_geometry_validation" && (
            <p className="mb-3 rounded-lg bg-[#FF3B30]/10 px-3 py-2 text-[13px] text-[#FF3B30]">{activeTask.errorMessage}</p>
          )}
          {activeTask?.renderMode === "precise" && activeTask.geometryValidation && (
            <div className={`mb-3 rounded-lg px-3 py-2 text-[12px] ${activeTask.geometryValidation.valid ? "bg-[#34C759]/10 text-[#248A3D]" : "bg-[#FF3B30]/10 text-[#C9342C]"}`}>
              <p className="font-semibold">
                {activeTask.geometryValidation.valid ? "DXF 结构检查通过" : "DXF 结构检查未通过"}
              </p>
              {activeTask.geometryValidation.valid && (
                <p className="mt-1 leading-5">门扇、门框、门套与五金位置按 DXF 实际几何生成，毫米尺寸不取自预览图。</p>
              )}
              {!activeTask.geometryValidation.valid && (
                <ul className="mt-1 space-y-1">
                  {activeTask.geometryValidation.errors.map((issue, index) => (
                    <li key={`${issue.code}-${issue.role}-${index}`}>
                      {renderGeometryRoleLabel(issue.role)}：{issue.message}{issue.layer ? `（图层 ${issue.layer}）` : ""}
                    </li>
                  ))}
                </ul>
              )}
              {activeTask.geometryValidation.warnings.length > 0 && (
                <ul className="mt-1 space-y-1 opacity-80">
                  {activeTask.geometryValidation.warnings.map((issue, index) => (
                    <li key={`warning-${issue.code}-${index}`}>提示：{issue.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {activeTask && (
            <div className="mb-3 flex flex-wrap gap-2 text-[11px]">
              <span className={`rounded-full px-2 py-1 font-medium ${activeTask.renderMode === "precise" ? "bg-[#007AFF]/10 text-[#007AFF]" : "bg-[#F2F2F7] text-[#636366]"}`}>
                {activeTask.renderMode === "precise" ? "精准分区" : "快速 AI"}
              </span>
              <span className="rounded-full bg-[#F2F2F7] px-2 py-1 text-[#636366]">{activeTask.sourceSide === "back" ? "反面" : "正面"}</span>
              {activeTask.renderMode === "precise" && <span className="rounded-full bg-[#F2F2F7] px-2 py-1 text-[#636366]">PSD：{activeTask.psdStatus === "completed" ? "已生成" : "未生成"}</span>}
            </div>
          )}
          {activeTask?.status === "completed" && activeTask.images?.length > 0 && (
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-[#E5E5EA] bg-[#F7F7FA] p-3">
              <span className="mr-1 text-[12px] font-semibold text-[#1C1C1E]">结果操作</span>
              {activeTask.renderMode === "precise" && REFERENCE_ROLE_OPTIONS.map((item) => (
                <button
                  key={item.role}
                  type="button"
                  onClick={() => void regenerateComponent(item.role)}
                  disabled={!taskRoleHasReferences(activeTask, item.role)}
                  className="rounded-lg border border-[#D1D1D6] bg-white px-3 py-1.5 text-[11px] font-medium text-[#3C3C43] disabled:cursor-not-allowed disabled:opacity-40"
                  title={taskRoleHasReferences(activeTask, item.role) ? `只重新生成${item.label}` : `${item.label}没有独立参考图`}
                >
                  重生成{item.label}
                </button>
              ))}
              <div className="flex-1" />
              {activeTask.psdStatus === "completed" && activeTask.psdFile?.url ? (
                <button type="button" onClick={() => void downloadPsd()} className="rounded-lg bg-[#1C1C1E] px-3 py-1.5 text-[12px] font-medium text-white">下载分层 PSD</button>
              ) : (
                <button type="button" onClick={() => void generatePsd()} className="rounded-lg bg-[#1C1C1E] px-3 py-1.5 text-[12px] font-medium text-white">生成分层 PSD</button>
              )}
            </div>
          )}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {(activeTask?.images || []).slice(0, 1).map((image) => (
              <div key={image.id} className="rounded-xl border border-[#E5E5EA] bg-[#F2F2F7] p-2">
                <button type="button" onClick={() => setPreviewImage({ src: image.src, title: "效果图" })} className="block w-full">
                  <img src={image.src} alt="效果图" className="max-h-[520px] w-full object-contain" />
                </button>
                <a href={image.src} download className="mt-2 inline-block rounded-lg bg-white px-3 py-1.5 text-[12px] font-medium text-[#007AFF]">下载</a>
              </div>
            ))}
            {!activeTask?.images?.length && <p className="text-[13px] text-[#8E8E93]">生成后的效果图会显示在这里</p>}
          </div>
        </div>
        <div className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
          <h2 className="mb-3 text-[15px] font-semibold text-[#1C1C1E]">历史记录</h2>
          <div className="space-y-2">
            {tasks.map((task) => (
              <div key={task.id} className={`rounded-lg px-3 py-2 text-[12px] ${activeTask?.id === task.id ? "bg-[#007AFF]/10 text-[#007AFF]" : "bg-[#F2F2F7] text-[#3C3C43]"}`}>
                <div className="flex items-start gap-2">
                  <button type="button" onClick={() => setActiveTask(task)} className="min-w-0 flex-1 cursor-pointer text-left">
                    <span className="font-medium">{task.status}</span>
                    <span className="ml-2 rounded-full bg-white px-1.5 py-0.5 text-[10px]">{task.renderMode === "precise" ? "精准" : "快速"}</span>
                    <span className="ml-2">{formatRenderTime(task.finishedAt || task.createdAt)}</span>
                    <span className="mt-1 block truncate text-[11px] opacity-70">{renderTaskModelText(task, configs)}</span>
                    {task.errorMessage && <span className="mt-1 block truncate text-[11px] text-[#FF3B30]">{task.errorMessage}</span>}
                  </button>
                  <button type="button" onClick={() => setActiveTask(task)} className="shrink-0 rounded-md bg-white px-2 py-1 text-[11px] font-medium text-[#007AFF]">查看</button>
                  <button type="button" onClick={() => removeTask(task.id)} className="shrink-0 rounded-md bg-white px-2 py-1 text-[11px] font-medium text-[#FF3B30]">删除</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

    </div>
  );
}

function UploadBox({ title, file, onPick, onPreview, required }: { title: string; file: File | null; onPick: (file: File | null) => void; onPreview: (src: string, title: string) => void; required?: boolean }) {
  function handlePaste(event: ClipboardEvent<HTMLLabelElement>) {
    const [pastedFile] = imageFilesFromClipboard(event);
    if (!pastedFile) return;
    event.preventDefault();
    onPick(pastedFile);
  }

  return (
    <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{title}{required ? " *" : ""}</h2>
        {file && <button type="button" onClick={() => onPick(null)} className="text-[12px] text-[#FF3B30]">清空</button>}
      </div>
      <label
        tabIndex={0}
        onPaste={handlePaste}
        className="flex min-h-[240px] cursor-pointer items-center justify-center rounded-xl border border-dashed border-[#C7C7CC] bg-[#F2F2F7] p-3 outline-none focus:border-[#007AFF]"
      >
        <input
          type="file"
          accept="image/*"
          onChange={(event) => {
            onPick(event.target.files?.[0] || null);
            event.currentTarget.value = "";
          }}
          className="hidden"
        />
        {file ? (
          <div className="w-full text-center">
            <FilePreviewImage file={file} className="mx-auto max-h-[220px] max-w-full rounded-lg object-contain" onPreview={onPreview} />
            <p className="mt-2 truncate text-[12px] text-[#3C3C43]">{file.name}</p>
            <p className="mt-1 text-[11px] text-[#8E8E93]">点击可重新上传，也可以 Ctrl+V 粘贴替换</p>
          </div>
        ) : (
          <span className="text-center text-[13px] text-[#8E8E93]">点击上传{title}，或 Ctrl+V 粘贴图片</span>
        )}
      </label>
    </section>
  );
}

function CompactDxfUpload({ file, busy, onPick }: { file: File | null; busy: boolean; onPick: (file: File | null) => void }) {
  return (
    <label className="flex min-h-20 cursor-pointer items-center rounded-xl border border-dashed border-[#C7C7CC] bg-[#F7F7FA] px-4 py-3">
      <input type="file" accept=".dxf,application/dxf" className="hidden" onChange={(event) => { onPick(event.target.files?.[0] || null); event.currentTarget.value = ""; }} />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-[#1C1C1E]">{busy ? "正在读取 DXF..." : file ? file.name : "点击上传 DXF 文件"}</p>
        <p className="mt-1 text-[11px] text-[#8E8E93]">精准模式直接读取门扇、门框、门套和五金图层</p>
      </div>
      {file && <button type="button" onClick={(event) => { event.preventDefault(); onPick(null); }} className="ml-3 rounded-lg bg-white px-3 py-1.5 text-[12px] text-[#FF3B30]">清空</button>}
    </label>
  );
}

function CompactSourceUpload({ file, onPick }: { file: File | null; onPick: (file: File | null) => void }) {
  function handlePaste(event: ClipboardEvent<HTMLLabelElement>) {
    const [pastedFile] = imageFilesFromClipboard(event);
    if (!pastedFile) return;
    event.preventDefault();
    onPick(pastedFile);
  }

  return (
    <label tabIndex={0} onPaste={handlePaste} className="flex min-h-20 cursor-pointer items-center rounded-xl border border-dashed border-[#C7C7CC] bg-[#F7F7FA] px-4 py-3 outline-none focus:border-[#007AFF]">
      <input
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          onPick(event.target.files?.[0] || null);
          event.currentTarget.value = "";
        }}
      />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-[#1C1C1E]">{file ? file.name : "点击上传完整订单图，或 Ctrl+V 粘贴"}</p>
        <p className="mt-1 text-[11px] text-[#8E8E93]">保留原图并自动提取正面、反面两个门体区域</p>
      </div>
      {file && <button type="button" onClick={(event) => { event.preventDefault(); onPick(null); }} className="ml-3 rounded-lg bg-white px-3 py-1.5 text-[12px] text-[#FF3B30]">清空</button>}
    </label>
  );
}

function CompactImageUpload({ files, onChange }: { files: File[]; onChange: (files: File[]) => void }) {
  function appendFiles(nextFiles: File[]) {
    if (!nextFiles.length) return;
    onChange(nextFiles);
  }

  function handlePaste(event: ClipboardEvent<HTMLLabelElement>) {
    const pastedFiles = imageFilesFromClipboard(event);
    if (!pastedFiles.length) return;
    event.preventDefault();
    appendFiles(pastedFiles);
  }

  return (
    <label
      tabIndex={0}
      onPaste={handlePaste}
      className="flex h-9 cursor-pointer items-center justify-center rounded-lg border border-dashed border-[#C7C7CC] bg-[#F2F2F7] px-2 text-[12px] font-medium text-[#3C3C43] outline-none focus:border-[#007AFF]"
      title="上传或 Ctrl+V 粘贴本组参考图"
    >
      上传图{files.length ? ` ${files.length}` : ""}
      <input
        type="file"
        accept="image/*"
        multiple
        onChange={(event) => {
          appendFiles(imageFilesFromList(event.target.files));
          event.currentTarget.value = "";
        }}
        className="hidden"
      />
    </label>
  );
}

function TempFileChip({ file, onPreview, onRemove }: { file: File; onPreview: (src: string, title: string) => void; onRemove: () => void }) {
  const src = useMemo(() => URL.createObjectURL(file), [file]);

  useEffect(() => {
    return () => URL.revokeObjectURL(src);
  }, [src]);

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[#F2F2F7] px-2 py-1 text-[11px] text-[#3C3C43]">
      <button type="button" onClick={() => src && onPreview(src, file.name)} className="max-w-[180px] truncate">
        {file.name}
      </button>
      <button type="button" onClick={onRemove} className="text-[#FF3B30]">×</button>
    </span>
  );
}

function LibraryUploadButton({ category, onUploaded }: { category: string; onUploaded: (asset: RenderAsset) => void }) {
  const [uploading, setUploading] = useState(false);

  async function uploadFiles(files: File[]) {
    if (!files.length || uploading) return;
    setUploading(true);
    try {
      for (const file of files) {
        const asset = await uploadRenderAsset({
          file,
          name: file.name.replace(/\.[^.]+$/, "") || file.name,
          category: category || "其他",
          favorite: true,
        });
        onUploaded(asset);
      }
    } finally {
      setUploading(false);
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLLabelElement>) {
    const files = imageFilesFromClipboard(event);
    if (!files.length) return;
    event.preventDefault();
    void uploadFiles(files);
  }

  return (
    <label
      tabIndex={0}
      onPaste={handlePaste}
      className="cursor-pointer rounded-lg bg-[#007AFF] px-3 py-2 text-[13px] font-medium text-white outline-none focus:ring-2 focus:ring-[#007AFF]/30"
    >
      {uploading ? "上传中..." : "上传素材"}
      <input
        type="file"
        accept="image/*"
        multiple
        disabled={uploading}
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          void uploadFiles(imageFilesFromList(event.target.files));
          event.currentTarget.value = "";
        }}
        className="hidden"
      />
    </label>
  );
}

function FilePreviewImage({ file, className, onPreview }: { file: File; className: string; onPreview?: (src: string, title: string) => void }) {
  const src = useMemo(() => URL.createObjectURL(file), [file]);

  useEffect(() => {
    return () => URL.revokeObjectURL(src);
  }, [src]);

  if (onPreview) {
    return (
      <button type="button" onClick={(event) => { event.preventDefault(); onPreview(src, file.name); }} className="inline-block max-w-full">
        <img src={src} alt={file.name} className={className} />
      </button>
    );
  }
  return <img src={src} alt={file.name} className={className} />;
}

function imageFilesFromList(fileList: FileList | null): File[] {
  return Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
}

function imageFilesFromClipboard(event: ClipboardEvent): File[] {
  const files = imageFilesFromList(event.clipboardData?.files || null);
  if (files.length) return files;
  return Array.from(event.clipboardData?.items || [])
    .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file));
}

function Input({ label, value, onChange, type = "text", placeholder = "" }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return <label><span className="text-[12px] font-medium text-[#8E8E93]">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" /></label>;
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return <label><span className="text-[12px] font-medium text-[#8E8E93]">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[13px]">{options.map(([optionValue, labelText]) => <option key={optionValue} value={optionValue}>{labelText}</option>)}</select></label>;
}

function formFromConfig(config: RenderModelConfig): ModelConfigInput {
  return {
    name: config.name,
    provider: config.provider,
    baseUrl: config.baseUrl,
    apiKey: "",
    model: config.model,
    endpoint: config.endpoint,
    apiType: config.apiType,
    defaultSize: config.defaultSize,
    timeoutSeconds: config.timeoutSeconds,
    enabled: config.enabled,
  };
}

function pickDefaultConfig(configs: RenderModelConfig[]): RenderModelConfig | undefined {
  return [...configs]
    .filter((item) => item.enabled)
    .sort((a, b) => String(b.updatedAt || b.createdAt || "").localeCompare(String(a.updatedAt || a.createdAt || "")))[0];
}

function taskRoleHasReferences(task: RenderTask, role: RenderReferenceRole): boolean {
  const binding = task.referenceBindings?.[role];
  return Boolean(binding?.assetIds?.length || binding?.files?.length);
}

function renderGeometryRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    panel: "门扇",
    frame: "门框",
    trim: "门套",
    hardware: "五金",
    outline: "结构图层",
  };
  return labels[role] || "DXF 结构";
}

function formatRenderTime(value: string): string {
  if (!value) return "";
  const normalized = /(?:z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function renderTaskModelText(task: RenderTask, configs: RenderModelConfig[]): string {
  const snapshot = task.modelConfigSnapshot || {};
  const fallbackConfig = configs.find((item) => item.id === task.modelConfigId);
  const source = Object.keys(snapshot).length ? snapshot : fallbackConfig || {};
  return renderConfigSummary(source) || task.modelConfigId;
}

function renderConfigSummary(config: Partial<RenderModelConfig> | NonNullable<RenderTask["modelConfigSnapshot"]>): string {
  return [config.name, config.provider, config.apiType, config.baseUrl, config.endpoint, config.model].filter(Boolean).join(" / ");
}

function isLiveRenderStatus(status: string): boolean {
  return ["pending", "running"].includes(String(status || "").toLowerCase());
}

function renderTaskStatusMessage(task: RenderTask): string {
  if (task.status === "completed") return "效果图生成完成";
  if (task.status === "failed") return task.errorMessage || "效果渲染失败";
  return "任务已提交，后端正在生成中，完成后会自动刷新结果";
}

function findRecentRenderTask(tasks: RenderTask[], sinceMs: number): RenderTask | null {
  return [...tasks]
    .filter((task) => {
      const createdAt = new Date(task.createdAt).getTime();
      return Number.isFinite(createdAt) && createdAt >= sinceMs - 5000;
    })
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())[0] || null;
}

function wait(ms: number): Promise<null> {
  return new Promise((resolve) => window.setTimeout(() => resolve(null), ms));
}

function clampCount(value: unknown): number {
  void value;
  return 1;
}
