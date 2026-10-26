"use client";

import { ClipboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { ImagePlus, Trash2 } from "lucide-react";
import dynamic from "next/dynamic";
import TaskProjectCombobox from "@/components/TaskProjectCombobox";
import { downloadFileFromUrl, getTasks } from "@/lib/api";
import type { TaskItem } from "@/lib/types";
import {
  RENDER_CATEGORIES,
  createRenderModelConfig,
  createRenderTask,
  deleteRenderAsset,
  deleteRenderModelConfig,
  deleteRenderTask,
  extractDxfLineArt,
  extractTaskLineArt,
  extractUploadedLineArt,
  lineArtViewToFile,
  listRenderAssets,
  listRenderModelConfigs,
  listRenderTasks,
  renderTaskFileToFile,
  updateRenderModelConfig,
  updateLineArtCrop,
  uploadRenderAsset,
  type ModelConfigInput,
  type RenderAsset,
  type RenderModelConfig,
  type RenderTask,
  type LineArtExtraction,
  type RenderReferenceRole,
} from "@/lib/renderApi";
import { restoreRenderHistory } from "@/lib/renderHistory";
import { renderCategoryLabel, renderCategoryRole } from "@/lib/renderAssetCategories";
import { clipboardImageFiles, isClipboardTextTarget } from "@/lib/clipboardImages";

const DEFAULT_PROMPT = "基于图纸生成清晰、真实的门类产品效果图。严格保持门型结构、比例和部件位置，以参考款式图为整体风格参考，配件素材仅用于对应部件、材质、颜色和细节。最终成图不显示 CAD 线稿、尺寸线、文字、标注箭头或辅助轮廓，玻璃和五金位于门扇表面上方，接缝表现为真实窄黑缝。";
const ASSET_PAGE_SIZE = 24;
const TASK_LIST_LIMIT = 20;
const REFERENCE_ROLE_OPTIONS: Array<{ role: RenderReferenceRole; label: string; description: string; required?: boolean }> = [
  { role: "panel", label: "门扇款式", description: "控制门扇内部款式、颜色和质感", required: true },
  { role: "trim", label: "门套款式", description: "控制门套的造型与材质" },
  { role: "frame", label: "门框材质", description: "为空时继承门扇颜色与材质" },
  { role: "glass", label: "玻璃", description: "控制玻璃颜色、透明度、纹理和反光" },
  { role: "hardware", label: "五金配件", description: "拉手、锁具、合页、花件及其他配件" },
];
const REFERENCE_ROLE_LABEL = Object.fromEntries(REFERENCE_ROLE_OPTIONS.map((item) => [item.role, item.label])) as Record<RenderReferenceRole, string>;

function resolveRenderSize(selectedSize: string) {
  return selectedSize === "auto" ? "2k" : selectedSize;
}
const LineArtCropEditor = dynamic(() => import("@/components/LineArtCropEditor"), {
  ssr: false,
  loading: () => <div className="flex min-h-72 items-center justify-center text-sm text-[#8E8E93]">正在加载裁剪工具...</div>,
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
  const [knownAssets, setKnownAssets] = useState<Record<string, RenderAsset>>({});
  const [tasks, setTasks] = useState<RenderTask[]>([]);
  const [modelConfigOpen, setModelConfigOpen] = useState(false);
  const [assetLibraryOpen, setAssetLibraryOpen] = useState(true);
  const [category, setCategory] = useState("门扇款式");
  const [search, setSearch] = useState("");
  const [assetOffset, setAssetOffset] = useState(0);
  const [assetHasMore, setAssetHasMore] = useState(false);
  const [assetLoading, setAssetLoading] = useState(false);
  const [referenceUploading, setReferenceUploading] = useState(false);
  const referenceUploadLock = useRef(false);
  const assetRequestId = useRef(0);
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
  const [psdDownloading, setPsdDownloading] = useState(false);
  const [referenceGroups, setReferenceGroups] = useState<ReferenceGroup[]>(() => createDefaultReferenceGroups());
  const [colorTargetRole, setColorTargetRole] = useState<RenderReferenceRole>("panel");
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
  const uploadCategory = category || "门扇款式";
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
        try {
          const initialAssets = await listRenderAssets({ category: "门扇款式", limit: ASSET_PAGE_SIZE }, controller.signal);
          if (cancelled || assetRequestId.current !== 0) return;
          setAssets(current => Array.from(new Map([...current, ...initialAssets].map(asset => [asset.id, asset])).values()));
          setKnownAssets(current => ({ ...current, ...Object.fromEntries(initialAssets.map(asset => [asset.id, asset])) }));
          setAssetOffset(initialAssets.length);
          setAssetHasMore(initialAssets.length === ASSET_PAGE_SIZE);
        } catch {
          if (!cancelled) setMessage("素材库暂时无法加载，请重新选择分类重试");
        }
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

  async function restoreHistoryTask(task: RenderTask) {
    setActiveTask(task);
    const restored = restoreRenderHistory(task);
    setSelectedConfigId(restored.configId);
    const restoredConfig = configs.find((item) => item.id === restored.configId);
    if (restoredConfig) {
      setEditingConfigId(restoredConfig.id);
      setConfigForm(formFromConfig(restoredConfig));
    }
    setPrompt(restored.prompt || DEFAULT_PROMPT);
    setSize(restored.size);
    setSelectedLineArtSide(restored.sourceSide);
    setSelectedDrawingTaskId(restored.sourceTaskId);
    setOrderSheet(null);
    setDxfFile(null);
    setLineArt(null);
    setLineArtExtraction(null);

    const warnings: string[] = [];
    const nextGroups = createDefaultReferenceGroups();
    for (const restoredGroup of restored.referenceGroups) {
      const index = nextGroups.findIndex((group) => group.role === restoredGroup.role);
      if (index < 0) continue;
      const restoredFiles: File[] = [];
      for (const storedFile of restoredGroup.persistedFiles) {
        try {
          restoredFiles.push(await renderTaskFileToFile(storedFile, `${restoredGroup.role}-reference.png`));
        } catch {
          warnings.push(`${REFERENCE_ROLE_LABEL[restoredGroup.role]}参考图无法恢复`);
        }
      }
      nextGroups[index] = {
        ...nextGroups[index],
        assetIds: restoredGroup.assetIds,
        files: restoredFiles,
      };
    }
    setReferenceGroups(nextGroups);

    const selectedAssetIds = Array.from(new Set(nextGroups.flatMap((group) => group.assetIds)));
    if (selectedAssetIds.length) {
      try {
        const availableAssets = await listRenderAssets({ limit: 200 });
        rememberAssets(availableAssets);
      } catch {
        warnings.push("素材库详情暂时无法加载");
      }
    }

    try {
      if (restored.sourceType === "task" && restored.sourceTaskId) {
        setLineArtSource("task");
        setLineArtExtraction(await extractTaskLineArt(restored.sourceTaskId));
      } else if (restored.sourceType === "dxf") {
        const storedDxf = task.files.find((file) => file.role === "source_dxf");
        if (!storedDxf) throw new Error("历史任务缺少 DXF 文件");
        const restoredDxf = await renderTaskFileToFile(storedDxf, "history-source.dxf");
        setLineArtSource("dxf");
        setDxfFile(restoredDxf);
        setLineArtExtraction(await extractDxfLineArt(restoredDxf));
      } else if (restored.lineArtFile) {
        setLineArtSource("direct");
        setLineArt(await renderTaskFileToFile(restored.lineArtFile, "history-line-art.png"));
      } else {
        throw new Error("历史任务缺少线稿文件");
      }
    } catch (error) {
      warnings.push((error as Error).message || "线稿无法恢复");
    }

    setMessage(warnings.length ? `已恢复历史任务；${Array.from(new Set(warnings)).join("；")}` : "已恢复该次线稿、参考素材和生成参数");
  }

  async function loadAssets(options: { reset?: boolean; categoryValue?: string; searchValue?: string } = {}) {
    const reset = Boolean(options.reset);
    const nextCategory = options.categoryValue ?? category;
    const nextSearch = options.searchValue ?? search;
    const nextOffset = reset ? 0 : assetOffset;
    const requestId = ++assetRequestId.current;
    setAssetLoading(true);
    try {
      const nextAssets = await listRenderAssets({
        category: nextCategory || undefined,
        q: nextSearch || undefined,
        limit: ASSET_PAGE_SIZE,
        offset: nextOffset,
      });
      if (requestId !== assetRequestId.current) return;
      setAssets((current) => reset ? nextAssets : Array.from(new Map([...current, ...nextAssets].map(asset => [asset.id, asset])).values()));
      rememberAssets(nextAssets);
      setAssetOffset(nextOffset + nextAssets.length);
      setAssetHasMore(nextAssets.length === ASSET_PAGE_SIZE);
    } catch (error) {
      if (requestId === assetRequestId.current) {
        setErrorDialog({ title: "素材库加载失败", message: (error as Error).message || "请稍后重试" });
      }
    } finally {
      if (requestId === assetRequestId.current) setAssetLoading(false);
    }
  }

  function rememberAssets(items: RenderAsset[]) {
    setKnownAssets(current => ({ ...current, ...Object.fromEntries(items.map(asset => [asset.id, asset])) }));
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
    setAssets([]);
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
    const targetRole = renderCategoryRole(asset.category, colorTargetRole);
    setReferenceGroups((current) => {
      const exists = current.some((group) => group.assetIds.includes(asset.id));
      if (exists) {
        return current.map((group) => ({ ...group, assetIds: group.assetIds.filter((id) => id !== asset.id) }));
      }
      const next = current.length ? [...current] : createDefaultReferenceGroups();
      const index = Math.max(0, next.findIndex((group) => group.role === targetRole));
      next[index] = { ...next[index], assetIds: [...next[index].assetIds, asset.id] };
      return next;
    });
  }

  function removeReferenceAsset(assetId: string) {
    setReferenceGroups((current) => current.map((group) => ({ ...group, assetIds: group.assetIds.filter((id) => id !== assetId) })));
  }

  function moveReferenceAsset(assetId: string, role: RenderReferenceRole) {
    setReferenceGroups(current => current.map(group => ({
      ...group,
      assetIds: group.role === role
        ? Array.from(new Set([...group.assetIds, assetId]))
        : group.assetIds.filter(id => id !== assetId),
    })));
  }

  function moveReferenceFile(file: File, role: RenderReferenceRole) {
    setReferenceGroups(current => current.map(group => ({
      ...group, files: group.role === role
        ? [...group.files.filter(item => item !== file), file]
        : group.files.filter(item => item !== file),
    })));
  }

  async function uploadReferenceImages(files: File[]) {
    if (!files.length || referenceUploadLock.current) return;
    referenceUploadLock.current = true;
    setReferenceUploading(true);
    const destination = uploadCategory;
    const targetRole = renderCategoryRole(destination, colorTargetRole);
    let completed = 0;
    try {
      for (const file of files) {
        const asset = await uploadRenderAsset({ file, name: file.name.replace(/\.[^.]+$/, "") || "截图",
          category: destination, favorite: true });
        rememberAssets([asset]);
        setAssets(current => [asset, ...current.filter(item => item.id !== asset.id)]);
        setAssetOffset(current => current + 1);
        setReferenceGroups(current => current.map(group => group.role === targetRole
          ? { ...group, assetIds: Array.from(new Set([...group.assetIds, asset.id])) } : group));
        completed += 1;
      }
      setMessage(`已上传并选用 ${completed} 张${destination}参考图`);
    } catch (error) {
      const failure = error as { userMessage?: string; message?: string };
      setErrorDialog({ title: "参考图上传失败", message: `已成功上传 ${completed} 张。${failure.userMessage || failure.message || "请稍后重试"}` });
    } finally {
      referenceUploadLock.current = false;
      setReferenceUploading(false);
    }
  }

  function pasteReferenceImages(event: ClipboardEvent<HTMLElement>) {
    if (isClipboardTextTarget(event.target)) return;
    const files = clipboardImageFiles(event.clipboardData);
    if (!files.length) return;
    event.preventDefault();
    event.stopPropagation();
    void uploadReferenceImages(files);
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

  async function submitTask() {
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
    setLoading(true);
    setSubmitConfigText("正在保存当前模型配置...");
    setMessage("正在保存当前模型配置...");
    const submittedAt = Date.now();
    setSubmitWatchSince(submittedAt);
    const taskAssetIds = Array.from(new Set(referenceGroups.flatMap((group) => group.assetIds)));
    const effectiveSize = resolveRenderSize(size);
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
          renderMode: "quick",
          sourceType: lineArtSource === "task" ? "task" : lineArtSource === "dxf" ? "dxf" : "image",
          sourceSide: selectedLineArtSide,
          sourceTaskId: lineArtSource === "task" ? selectedDrawingTaskId : "",
          referenceBindings,
          referenceFiles,
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
      setMessage(task.status === "completed" ? "效果图生成完成" : `任务状态：${task.status}`);
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

  async function downloadHistoricalPsd() {
    if (!activeTask?.psdFile?.url) return;
    try {
      setPsdDownloading(true);
      await downloadFileFromUrl(activeTask.psdFile.url, activeTask.psdFile.originalName || `${activeTask.id}-分层效果图.psd`);
      setMessage("分层 PSD 已开始下载");
    } catch (error) {
      setErrorDialog({ title: "PSD 下载失败", message: (error as Error).message || "请稍后重试" });
    } finally {
      setPsdDownloading(false);
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
              onClick={() => { setLineArtSource(value); setLineArtExtraction(null); }}
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
              <TaskProjectCombobox tasks={drawingTasks} value={selectedDrawingTaskId} onChange={(value) => { setSelectedDrawingTaskId(value); setLineArtExtraction(null); }} />
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
          <UploadBox title="线稿图" file={lineArt} onPick={setLineArt} onPreview={(src, title) => setPreviewImage({ src, title })} required />
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
      </section>

      <section
        aria-label="参考素材"
        tabIndex={0}
        onPaste={pasteReferenceImages}
        className="rounded-lg border border-[#E5E5EA]/60 bg-white p-4 outline-none focus-within:border-[#007AFF]/40"
        title="选择分类后，在此区域按 Ctrl+V 粘贴截图"
      >
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => void toggleAssetLibrary()} className="text-left">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{assetLibraryOpen ? "▼" : "▶"} 参考素材</h2>
          </button>
          <div className="flex-1" />
          <button type="button" disabled={referenceUploading} onClick={() => { setAssetLibraryOpen(true); void handleCategoryChange(""); }} className={`text-[12px] ${category ? "text-[#636366]" : "font-semibold text-[#007AFF]"}`}>全部素材</button>
          <input
            value={search}
            aria-label="搜索素材"
            disabled={referenceUploading}
            onChange={(event) => setSearch(event.target.value)}
            onBlur={handleSearchBlur}
            onKeyDown={(event) => { if (event.key === "Enter") { setAssetLibraryOpen(true); void handleSearchBlur(); } }}
            placeholder="搜索素材"
            className="h-9 min-w-0 max-w-full rounded-md border border-[#E5E5EA] px-3 text-[13px]"
          />
          <label className={`inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-md bg-[#007AFF] px-3 py-2 text-[12px] font-medium text-white ${referenceUploading ? "opacity-50" : ""}`}>
            <ImagePlus size={16} aria-hidden="true" />
            {referenceUploading ? "上传中..." : `上传${uploadCategory}`}
            <input aria-label={`上传${uploadCategory}参考图`} type="file" accept="image/*" multiple disabled={referenceUploading} className="hidden"
              onChange={(event) => { void uploadReferenceImages(imageFilesFromList(event.target.files)); event.currentTarget.value = ""; }} />
          </label>
        </div>

        <div role="tablist" aria-label="素材分类" className="mb-3 grid grid-cols-2 gap-1 border-b border-[#E5E5EA] pb-3 sm:grid-cols-3 xl:grid-cols-6">
          {RENDER_CATEGORIES.map(item => (
            <button key={item} role="tab" aria-selected={category === item} type="button" disabled={referenceUploading}
              onClick={() => { setAssetLibraryOpen(true); void handleCategoryChange(item); }}
              className={`min-h-9 rounded-md px-3 py-2 text-[13px] font-medium disabled:opacity-50 ${category === item ? "bg-[#007AFF]/10 text-[#007AFF]" : "text-[#636366] hover:bg-[#F2F2F7]"}`}>
              {item}
            </button>
          ))}
        </div>
        {(category === "颜色" || !category) && (
          <div className="mb-3 max-w-xs">
            <Select label="颜色作用部件" value={colorTargetRole} onChange={value => setColorTargetRole(value as RenderReferenceRole)} options={REFERENCE_ROLE_OPTIONS.map(item => [item.role, item.label])} />
          </div>
        )}

        {assetLibraryOpen && (
          <>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" aria-busy={assetLoading}>
                {assets.map((asset) => {
                  const selected = selectedReferenceAssetIds.includes(asset.id);
                  return (
                    <div key={asset.id} className={`grid grid-cols-[88px_minmax(0,1fr)] gap-3 rounded-lg border p-2 ${selected ? "border-[#007AFF] bg-[#007AFF]/5" : "border-[#E5E5EA]"}`}>
                      <button
                        type="button"
                        onClick={() => setPreviewImage({ src: asset.url || asset.thumbnailUrl, title: asset.name })}
                        className="aspect-square rounded-lg bg-[#F2F2F7]"
                      >
                        <img src={asset.thumbnailUrl || asset.url} alt={asset.name} loading="lazy" decoding="async" className="h-full w-full object-contain" />
                      </button>
                      <div className="min-w-0">
                        <p className="truncate text-left text-[13px] font-medium text-[#1C1C1E]">{asset.name}</p>
                        <p className="mt-1 truncate text-left text-[12px] text-[#8E8E93]">{renderCategoryLabel(asset.category)}</p>
                        <div className="mt-4 flex gap-2">
                          <button
                            type="button"
                            onClick={() => toggleReferenceAsset(asset)}
                            className={`flex-1 rounded-lg px-2 py-1.5 text-[12px] font-medium ${selected ? "bg-[#007AFF] text-white" : "bg-[#F2F2F7] text-[#1C1C1E]"}`}
                          >
                            {selected ? "已选" : `选用 · ${REFERENCE_ROLE_LABEL[renderCategoryRole(asset.category, colorTargetRole)]}`}
                          </button>
                          <button type="button" onClick={() => removeAsset(asset.id)} title={`删除${asset.name}`} aria-label={`删除素材${asset.name}`} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#FF3B30] hover:bg-[#FF3B30]/5"><Trash2 size={15} /></button>
                        </div>
                      </div>
                    </div>
                  );
                })}
                {assetLoading && <p className="col-span-full text-[13px] text-[#8E8E93]">素材加载中...</p>}
                {!assetLoading && !assets.length && <p className="col-span-full text-[13px] text-[#8E8E93]">暂无素材</p>}
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

        <div className="mt-3 border-t border-[#E5E5EA] pt-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <div className="text-[13px] font-semibold text-[#1C1C1E]">已选参考图</div>
            <span className="text-[12px] text-[#8E8E93]">{selectedReferenceAssetCount + uploadedReferenceFileCount} 张</span>
          </div>
          {(selectedReferenceAssetIds.length > 0 || selectedReferenceFiles.length > 0) ? (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
              {selectedReferenceAssetIds.map((assetId) => {
                const asset = knownAssets[assetId];
                const role = referenceGroups.find((group) => group.assetIds.includes(assetId))?.role;
                return (
                  <div key={assetId} className="flex min-w-0 items-center gap-2 border-b border-[#E5E5EA]/60 py-2 text-[11px] text-[#3C3C43]">
                    <button
                      type="button"
                      onClick={() => asset && setPreviewImage({ src: asset.url || asset.thumbnailUrl, title: asset.name })}
                      className="min-w-0 flex-1 text-left"
                    >
                      {asset && <img src={asset.thumbnailUrl || asset.url} alt="" className="float-left mr-2 h-10 w-10 rounded-md bg-[#F2F2F7] object-contain" />}
                      <span className="block truncate">{asset?.name || assetId}</span>
                    </button>
                    <select aria-label={`${asset?.name || assetId}作用部件`} value={role || "panel"} onChange={event => moveReferenceAsset(assetId, event.target.value as RenderReferenceRole)} className="min-w-0 max-w-[110px] rounded-md border border-[#E5E5EA] bg-white px-1 py-1 text-[11px]">
                      {REFERENCE_ROLE_OPTIONS.map(item => <option key={item.role} value={item.role}>{item.label}</option>)}
                    </select>
                    <button type="button" onClick={() => removeReferenceAsset(assetId)} title="移除参考图" aria-label={`移除参考图${asset?.name || assetId}`} className="shrink-0 text-[#FF3B30]">×</button>
                  </div>
                );
              })}
              {referenceGroups.flatMap((group) => group.files.map((file, index) => (
                  <div key={`${group.role}-${file.name}-${file.lastModified}-${index}`} className="flex min-w-0 items-center gap-2 border-b border-[#E5E5EA]/60 py-2 text-[11px] text-[#3C3C43]">
                    <TempFileChip file={file} onPreview={(src, title) => setPreviewImage({ src, title })} onRemove={() => removeReferenceFile(file)} />
                    <select aria-label={`${file.name}作用部件`} value={group.role} onChange={event => moveReferenceFile(file, event.target.value as RenderReferenceRole)} className="min-w-0 max-w-[110px] rounded-md border border-[#E5E5EA] bg-white px-1 py-1 text-[11px]">
                      {REFERENCE_ROLE_OPTIONS.map(item => <option key={item.role} value={item.role}>{item.label}</option>)}
                    </select>
                  </div>
                ))) }
            </div>
          ) : (
            <p className="text-[12px] text-[#8E8E93]">未选择参考图</p>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_160px_120px]">
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">提示词</span>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" />
          </label>
          <Select label="输出清晰度" value={size} onChange={setSize} options={[["auto", "自动（2K）"], ["1k", "1K"], ["2k", "2K"], ["4k", "4K"]]} />
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">数量</span>
            <input type="number" min={1} max={1} value={count} disabled onChange={(event) => setCount(clampCount(event.target.value))} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px] disabled:bg-[#F2F2F7]" />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="text-[12px] text-[#8E8E93]">已选素材 {selectedReferenceAssetCount} 个，本次上传参考图 {uploadedReferenceFileCount} 个</span>
          <div className="flex-1" />
          <button type="button" onClick={() => void submitTask()} disabled={loading} className="rounded-lg bg-[#007AFF] px-5 py-2 text-[13px] font-medium text-white disabled:opacity-50">
            {loading ? "提交中..." : `一键生成效果图 · ${resolveRenderSize(size).toUpperCase()}`}
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
                {activeTask.renderMode === "precise" ? "历史分区结果" : "快速 AI"}
              </span>
              <span className="rounded-full bg-[#F2F2F7] px-2 py-1 text-[#636366]">{activeTask.sourceSide === "back" ? "反面" : "正面"}</span>
              <span className={`rounded-full px-2 py-1 ${activeTask.materialMode === "ai" ? "bg-[#34C759]/10 text-[#248A3D]" : "bg-[#FF9F0A]/10 text-[#A05A00]"}`}>
                {activeTask.materialMode === "ai" ? "AI 材质" : "平整材质"}
              </span>
              {activeTask.renderMode === "precise" && <span className="rounded-full bg-[#F2F2F7] px-2 py-1 text-[#636366]">PSD：{activeTask.psdStatus === "completed" ? "已生成" : "未生成"}</span>}
            </div>
          )}
          {activeTask?.materialNote && (
            <div className={`mb-3 rounded-xl border px-3 py-2 text-[12px] ${activeTask.materialMode === "flat" ? "border-[#FF9F0A]/30 bg-[#FF9F0A]/5 text-[#8A4B00]" : "border-[#007AFF]/20 bg-[#007AFF]/5 text-[#3C3C43]"}`}>
              {activeTask.materialNote}
            </div>
          )}
          {activeTask?.status === "completed" && activeTask.psdFile?.url && (
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-[#E5E5EA] bg-[#F7F7FA] p-3">
              <span className="mr-1 text-[12px] font-semibold text-[#1C1C1E]">结果操作</span>
              <div className="flex-1" />
              <button
                type="button"
                onClick={() => void downloadHistoricalPsd()}
                disabled={psdDownloading}
                className="min-w-[132px] rounded-lg bg-[#1C1C1E] px-3 py-1.5 text-[12px] font-medium text-white disabled:cursor-wait disabled:opacity-60"
              >
                {psdDownloading ? "正在下载 PSD..." : "下载分层 PSD"}
              </button>
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
                  <button type="button" onClick={() => void restoreHistoryTask(task)} className="min-w-0 flex-1 cursor-pointer text-left">
                    <span className="font-medium">{task.status}</span>
                    <span className="ml-2 rounded-full bg-white px-1.5 py-0.5 text-[10px]">{task.renderMode === "precise" ? "历史分区" : "快速"}</span>
                    <span className="ml-2">{formatRenderTime(task.finishedAt || task.createdAt)}</span>
                    <span className="mt-1 block truncate text-[11px] opacity-70">{renderTaskModelText(task, configs)}</span>
                    {task.errorMessage && <span className="mt-1 block truncate text-[11px] text-[#FF3B30]">{task.errorMessage}</span>}
                  </button>
                  <button type="button" onClick={() => void restoreHistoryTask(task)} className="shrink-0 rounded-md bg-white px-2 py-1 text-[11px] font-medium text-[#007AFF]">查看</button>
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
        <p className="mt-1 text-[11px] text-[#8E8E93]">DXF 格式</p>
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

function TempFileChip({ file, onPreview, onRemove }: { file: File; onPreview: (src: string, title: string) => void; onRemove: () => void }) {
  const src = useMemo(() => URL.createObjectURL(file), [file]);

  useEffect(() => {
    return () => URL.revokeObjectURL(src);
  }, [src]);

  return (
    <span className="inline-flex min-w-0 flex-1 items-center gap-1 text-[11px] text-[#3C3C43]">
      <button type="button" onClick={() => src && onPreview(src, file.name)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
        <img src={src} alt="" className="h-10 w-10 shrink-0 rounded-md bg-[#F2F2F7] object-contain" />
        <span className="truncate">{file.name}</span>
      </button>
      <button type="button" onClick={onRemove} className="text-[#FF3B30]">×</button>
    </span>
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
  return clipboardImageFiles(event.clipboardData);
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
