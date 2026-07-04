"use client";

import { ChangeEvent, ClipboardEvent, useEffect, useState } from "react";
import {
  RENDER_CATEGORIES,
  createRenderModelConfig,
  createRenderTask,
  deleteRenderAsset,
  deleteRenderModelConfig,
  deleteRenderTask,
  listRenderAssets,
  listRenderModelConfigs,
  listRenderTasks,
  updateRenderModelConfig,
  uploadRenderAsset,
  type ModelConfigInput,
  type RenderAsset,
  type RenderModelConfig,
  type RenderTask,
} from "@/lib/renderApi";

const DEFAULT_PROMPT = "基于线稿图生成门类产品效果图。保持门型结构、比例和主要线条，以参考款式图为整体风格参考，配件素材仅用于对应部件、材质、颜色和细节参考，输出真实产品渲染效果。";
const ASSET_PAGE_SIZE = 24;
const TASK_LIST_LIMIT = 20;
const DEFAULT_REFERENCE_GROUPS = ["款式", "拉手", "花件", "合页"];

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
  label: string;
  category: string;
  assetIds: string[];
  files: File[];
}

function createDefaultReferenceGroups(): ReferenceGroup[] {
  return DEFAULT_REFERENCE_GROUPS.map((category) => ({
    id: `${category}-${Math.random().toString(36).slice(2, 8)}`,
    label: category,
    category,
    assetIds: [],
    files: [],
  }));
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
  const [styleReference, setStyleReference] = useState<File | null>(null);
  const [referenceGroups, setReferenceGroups] = useState<ReferenceGroup[]>(() => createDefaultReferenceGroups());
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [size, setSize] = useState("original");
  const [count, setCount] = useState(1);
  const [activeTask, setActiveTask] = useState<RenderTask | null>(null);
  const [message, setMessage] = useState("");
  const [errorDialog, setErrorDialog] = useState<{ title: string; message: string; raw?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitConfigText, setSubmitConfigText] = useState("");
  const selectedConfig = configs.find((item) => item.id === selectedConfigId);
  const selectedReferenceAssetCount = referenceGroups.reduce((sum, group) => sum + group.assetIds.length, 0);
  const uploadedReferenceFileCount = referenceGroups.reduce((sum, group) => sum + group.files.length, 0);

  useEffect(() => {
    refreshAll();
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

  useEffect(() => {
    if (assetLibraryOpen && !assets.length && !assetLoading) {
      void loadAssets({ reset: true });
    }
  }, [assetLibraryOpen]);

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
    setConfigForm({ ...formFromConfig(saved), apiKey: "" });
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

  function updateReferenceGroup(groupId: string, patch: Partial<ReferenceGroup>) {
    setReferenceGroups((current) => current.map((group) => group.id === groupId ? { ...group, ...patch } : group));
  }

  function addReferenceGroup() {
    setReferenceGroups((current) => [
      ...current,
      {
        id: `ref-${Date.now()}`,
        label: "",
        category: "其他",
        assetIds: [],
        files: [],
      },
    ]);
  }

  function removeReferenceGroup(groupId: string) {
    setReferenceGroups((current) => current.filter((group) => group.id !== groupId));
  }

  async function submitTask() {
    if (!lineArt) return setMessage("请上传线稿图");
    if (!styleReference) return setMessage("请上传参考款式图");
    if (!prompt.trim()) return setMessage("请填写提示词");
    setLoading(true);
    setSubmitConfigText("正在保存当前模型配置...");
    setMessage("正在保存当前模型配置...");
    const submittedAt = Date.now();
    const taskAssetIds = Array.from(new Set(referenceGroups.flatMap((group) => group.assetIds)));
    const taskTempAssets = referenceGroups.flatMap((group) => group.files);
    try {
      const saved = await saveConfig({ silent: true });
      if (!saved) {
        setLoading(false);
        return;
      }
      const submitSummary = renderConfigSummary(saved);
      setSubmitConfigText(submitSummary);
      setMessage(`正在提交渲染任务：${submitSummary}`);
      const task = await createRenderTask({
        modelConfigId: saved.id,
        prompt,
        size,
        count: 1,
        selectedAssetIds: taskAssetIds,
        lineArt,
        styleReference,
        tempAssets: taskTempAssets,
      });
      setActiveTask(task);
      setTasks(await listRenderTasks());
      setMessage(task.status === "completed" ? "效果图生成完成" : `任务状态：${task.status}`);
    } catch (error: unknown) {
      const err = error as { userMessage?: string; message?: string; task?: RenderTask; raw?: string };
      const text = err.userMessage || err.message || "效果渲染失败";
      const latestTasks = await listRenderTasks();
      setTasks(latestTasks);
      const freshTask = latestTasks.find((task) => {
        const createdAt = new Date(task.createdAt).getTime();
        return Number.isFinite(createdAt) && createdAt >= submittedAt - 5000;
      });
      const recoverableTask = freshTask && freshTask.status !== "failed" ? freshTask : null;
      if (recoverableTask) {
        setActiveTask(recoverableTask);
        setMessage(recoverableTask.status === "completed" ? "效果图生成完成" : "任务仍在生成中，请稍后刷新");
        return;
      }
      if (err.task) {
        setActiveTask(err.task);
      }
      setMessage(text);
      setErrorDialog({ title: "效果渲染失败", message: text, raw: err.raw || err.task?.upstreamRawError || "" });
    } finally {
      setLoading(false);
    }
  }

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
      {loading && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-white/65 px-4 backdrop-blur-[2px]">
          <div className="w-full max-w-md rounded-2xl border border-[#E5E5EA] bg-white p-5 text-center shadow-xl">
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
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => setAssetLibraryOpen((value) => !value)} className="text-left">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{assetLibraryOpen ? "▼" : "▶"} 个人素材库</h2>
            <p className="mt-1 text-[12px] text-[#8E8E93]">常用配件永久保存；本次渲染要用的参考图在下方配件模型区选择。</p>
          </button>
          <div className="flex-1" />
          {assetLibraryOpen && (
            <>
              <select value={category} onChange={(event) => void handleCategoryChange(event.target.value)} className="rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[13px]">
                <option value="">全部分类</option>
                {RENDER_CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <input value={search} onChange={(event) => setSearch(event.target.value)} onBlur={handleSearchBlur} placeholder="搜索素材" className="rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" />
              <LibraryUploadButton category={category} onUploaded={(asset) => { setAssets((current) => [asset, ...current]); setMessage("素材已上传到个人素材库"); }} />
            </>
          )}
        </div>
        {assetLibraryOpen && (
          <>
            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
              {assets.map((asset) => (
                <div key={asset.id} className="rounded-xl border border-[#E5E5EA] p-2">
                  <div className="aspect-square rounded-lg bg-[#F2F2F7]"><img src={asset.thumbnailUrl || asset.url} alt={asset.name} loading="lazy" decoding="async" className="h-full w-full object-contain" /></div>
                  <p className="mt-2 truncate text-left text-[12px] font-medium text-[#1C1C1E]">{asset.name}</p>
                  <p className="truncate text-left text-[11px] text-[#8E8E93]">{asset.category}</p>
                  <button type="button" onClick={() => removeAsset(asset.id)} className="mt-1 text-[11px] text-[#FF3B30]">删除</button>
                </div>
              ))}
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
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <UploadBox title="线稿图" file={lineArt} onPick={(file) => setLineArt(file)} required />
        <UploadBox title="参考款式图" file={styleReference} onPick={(file) => setStyleReference(file)} required />
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">参考配件模型</h2>
            <p className="mt-1 text-[12px] text-[#8E8E93]">每一组都可以从个人素材库选择，也可以粘贴或上传本次专用参考图。</p>
          </div>
          <button type="button" onClick={addReferenceGroup} className="rounded-lg bg-[#F2F2F7] px-3 py-2 text-[13px] font-medium text-[#1C1C1E]">+ 增加参考项</button>
        </div>
        <div className="space-y-3">
          {referenceGroups.map((group) => {
            const libraryOptions = assets.filter((asset) => !group.category || asset.category === group.category);
            return (
              <div key={group.id} className="rounded-xl border border-[#E5E5EA] p-3">
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-[160px_160px_1fr_auto]">
                  <Input label="参考项" value={group.label} onChange={(value) => updateReferenceGroup(group.id, { label: value })} />
                  <Select label="分类" value={group.category} onChange={(value) => updateReferenceGroup(group.id, { category: value, assetIds: [] })} options={RENDER_CATEGORIES.map((item) => [item, item])} />
                  <label>
                    <span className="text-[12px] font-medium text-[#8E8E93]">从个人素材库选择</span>
                    <select
                      multiple
                      value={group.assetIds}
                      onChange={(event) => updateReferenceGroup(group.id, { assetIds: Array.from(event.target.selectedOptions).map((option) => option.value) })}
                      className="mt-1 h-20 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[13px]"
                    >
                      {libraryOptions.map((asset) => <option key={asset.id} value={asset.id}>{asset.name}</option>)}
                    </select>
                  </label>
                  <div className="flex items-end">
                    <button type="button" onClick={() => removeReferenceGroup(group.id)} className="h-9 rounded-lg bg-[#F2F2F7] px-3 text-[13px] text-[#FF3B30]">删除</button>
                  </div>
                </div>
                <MultiImageUploadBox
                  files={group.files}
                  onChange={(files) => updateReferenceGroup(group.id, { files })}
                />
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_160px_120px]">
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">提示词</span>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" />
          </label>
          <Select label="尺寸" value={size} onChange={setSize} options={[["original", "原比例"], ["1k", "1K"], ["2k", "2K"], ["4k", "4K"], ["1024x1024", "1024x1024"]]} />
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">数量</span>
            <input type="number" min={1} max={1} value={count} disabled onChange={(event) => setCount(clampCount(event.target.value))} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px] disabled:bg-[#F2F2F7]" />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="text-[12px] text-[#8E8E93]">已选素材 {selectedReferenceAssetCount} 个，本次上传参考图 {uploadedReferenceFileCount} 个</span>
          <div className="flex-1" />
          <button type="button" onClick={submitTask} disabled={loading} className="rounded-lg bg-[#007AFF] px-5 py-2 text-[13px] font-medium text-white disabled:opacity-50">{loading ? "生成中..." : "提交渲染任务"}</button>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <div className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">生成结果</h2>
            <button type="button" onClick={() => refreshAll()} className="rounded-lg bg-[#F2F2F7] px-3 py-1.5 text-[12px]">刷新</button>
          </div>
          {activeTask?.status === "failed" && <p className="mb-3 rounded-lg bg-[#FF3B30]/10 px-3 py-2 text-[13px] text-[#FF3B30]">{activeTask.errorMessage}</p>}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {(activeTask?.images || []).slice(0, 1).map((image) => (
              <div key={image.id} className="rounded-xl border border-[#E5E5EA] bg-[#F2F2F7] p-2">
                <img src={image.src} alt="效果图" className="max-h-[520px] w-full object-contain" />
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

function UploadBox({ title, file, onPick, required }: { title: string; file: File | null; onPick: (file: File | null) => void; required?: boolean }) {
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
            <FilePreviewImage file={file} className="mx-auto max-h-[220px] max-w-full rounded-lg object-contain" />
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

function MultiImageUploadBox({ files, onChange }: { files: File[]; onChange: (files: File[]) => void }) {
  function appendFiles(nextFiles: File[]) {
    if (!nextFiles.length) return;
    onChange([...files, ...nextFiles]);
  }

  function handlePaste(event: ClipboardEvent<HTMLLabelElement>) {
    const pastedFiles = imageFilesFromClipboard(event);
    if (!pastedFiles.length) return;
    event.preventDefault();
    appendFiles(pastedFiles);
  }

  return (
    <div className="mt-3">
      <label
        tabIndex={0}
        onPaste={handlePaste}
        className="block cursor-pointer rounded-xl border border-dashed border-[#C7C7CC] bg-[#F2F2F7] p-3 outline-none focus:border-[#007AFF]"
      >
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
        <span className="block text-[12px] font-medium text-[#3C3C43]">上传或粘贴本组参考图</span>
        <span className="mt-1 block text-[11px] text-[#8E8E93]">支持多张图片，Ctrl+V 可直接粘贴</span>
      </label>
      {files.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-6">
          {files.map((file, index) => (
            <div key={`${file.name}-${file.lastModified}-${index}`} className="rounded-lg border border-[#E5E5EA] bg-white p-2">
              <FilePreviewImage file={file} className="h-24 w-full rounded-md object-contain" />
              <p className="mt-1 truncate text-[11px] text-[#3C3C43]">{file.name}</p>
              <button type="button" onClick={() => onChange(files.filter((_, fileIndex) => fileIndex !== index))} className="mt-1 text-[11px] text-[#FF3B30]">删除</button>
            </div>
          ))}
        </div>
      )}
    </div>
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

function FilePreviewImage({ file, className }: { file: File; className: string }) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  if (!src) return null;
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

function clampCount(value: unknown): number {
  return 1;
}
