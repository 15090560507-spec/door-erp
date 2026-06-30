"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import {
  RENDER_CATEGORIES,
  createRenderModelConfig,
  createRenderTask,
  deleteRenderAsset,
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

const EMPTY_CONFIG: ModelConfigInput = {
  name: "",
  provider: "image2_proxy",
  baseUrl: "",
  apiKey: "",
  model: "",
  endpoint: "/images/edits",
  apiType: "openai_images_edits",
  defaultSize: "original",
  timeoutSeconds: 180,
  enabled: true,
};

export default function RenderPage() {
  const [configs, setConfigs] = useState<RenderModelConfig[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState("");
  const [configForm, setConfigForm] = useState<ModelConfigInput>(EMPTY_CONFIG);
  const [editingConfigId, setEditingConfigId] = useState("");
  const [assets, setAssets] = useState<RenderAsset[]>([]);
  const [tasks, setTasks] = useState<RenderTask[]>([]);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);
  const [lineArt, setLineArt] = useState<File | null>(null);
  const [styleReference, setStyleReference] = useState<File | null>(null);
  const [tempAssets, setTempAssets] = useState<File[]>([]);
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [size, setSize] = useState("original");
  const [count, setCount] = useState(1);
  const [activeTask, setActiveTask] = useState<RenderTask | null>(null);
  const [message, setMessage] = useState("");
  const [errorDialog, setErrorDialog] = useState<{ title: string; message: string; raw?: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const selectedConfig = configs.find((item) => item.id === selectedConfigId);

  useEffect(() => {
    refreshAll();
  }, []);

  async function refreshAll() {
    const [nextConfigs, nextAssets, nextTasks] = await Promise.all([
      listRenderModelConfigs(true),
      listRenderAssets(),
      listRenderTasks(),
    ]);
    setConfigs(nextConfigs);
    setAssets(nextAssets);
    setTasks(nextTasks);
    setSelectedConfigId((current) => current || nextConfigs.find((item) => item.enabled)?.id || "");
    setActiveTask((current) => current || nextTasks[0] || null);
  }

  async function refreshAssets() {
    setAssets(await listRenderAssets({ category: category || undefined, q: search || undefined }));
  }

  async function saveConfig() {
    if (!configForm.name.trim() || !configForm.baseUrl.trim() || !configForm.model.trim()) {
      return setMessage("请填写配置名称、Base URL 和 Model");
    }
    const saved = editingConfigId
      ? await updateRenderModelConfig(editingConfigId, configForm)
      : await createRenderModelConfig(configForm);
    const nextConfigs = await listRenderModelConfigs(true);
    setConfigs(nextConfigs);
    setSelectedConfigId(saved.id);
    setEditingConfigId("");
    setConfigForm(EMPTY_CONFIG);
    setMessage("模型配置已保存");
  }

  function editConfig(config: RenderModelConfig) {
    setEditingConfigId(config.id);
    setConfigForm({
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
    });
  }

  async function uploadAsset(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const name = window.prompt("素材名称", file.name.replace(/\.[^.]+$/, "")) || file.name;
    const asset = await uploadRenderAsset({ file, name, category: category || "其他", favorite: true });
    setAssets((current) => [asset, ...current]);
    setMessage("素材已上传到个人素材库");
  }

  async function removeAsset(assetId: string) {
    await deleteRenderAsset(assetId);
    setAssets((current) => current.filter((item) => item.id !== assetId));
    setSelectedAssetIds((current) => current.filter((id) => id !== assetId));
  }

  async function submitTask() {
    if (!selectedConfigId) return setMessage("请先选择模型配置");
    if (!lineArt) return setMessage("请上传线稿图");
    if (!styleReference) return setMessage("请上传参考款式图");
    if (!prompt.trim()) return setMessage("请填写提示词");
    setLoading(true);
    setMessage("正在提交渲染任务...");
    try {
      const task = await createRenderTask({
        modelConfigId: selectedConfigId,
        prompt,
        size,
        count,
        selectedAssetIds,
        lineArt,
        styleReference,
        tempAssets,
      });
      setActiveTask(task);
      setTasks(await listRenderTasks());
      setMessage(task.status === "completed" ? "效果图生成完成" : `任务状态：${task.status}`);
    } catch (error: unknown) {
      const err = error as { userMessage?: string; message?: string; task?: RenderTask; raw?: string };
      const text = err.userMessage || err.message || "效果渲染失败";
      if (err.task) {
        setActiveTask(err.task);
        setTasks(await listRenderTasks());
      }
      setMessage(text);
      setErrorDialog({ title: "效果渲染失败", message: text, raw: err.raw || err.task?.upstreamRawError || "" });
    } finally {
      setLoading(false);
    }
  }

  const filteredAssets = useMemo(() => {
    const q = search.trim().toLowerCase();
    return assets.filter((item) => {
      if (category && item.category !== category) return false;
      if (!q) return true;
      return [item.name, item.category, item.remark, ...(item.tags || [])].join(" ").toLowerCase().includes(q);
    });
  }, [assets, category, search]);

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

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E]">模型配置</h2>
          <select value={selectedConfigId} onChange={(event) => setSelectedConfigId(event.target.value)} className="rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[13px]">
            <option value="">选择模型配置</option>
            {configs.filter((item) => item.enabled).map((config) => <option key={config.id} value={config.id}>{config.name}</option>)}
          </select>
        </div>
        {selectedConfig && <p className="mb-3 text-[12px] text-[#8E8E93]">当前：{selectedConfig.provider} / {selectedConfig.apiType} / {selectedConfig.model} / API Key {selectedConfig.hasApiKey ? "已保存" : "未保存"}</p>}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          <Input label="配置名称" value={configForm.name} onChange={(value) => setConfigForm({ ...configForm, name: value })} />
          <Select label="Provider" value={configForm.provider} onChange={(value) => setConfigForm({ ...configForm, provider: value })} options={[["image2_proxy", "Image2 中转站"], ["openai_compatible", "OpenAI 兼容"], ["volcengine_ark", "火山方舟"]]} />
          <Input label="Base URL" value={configForm.baseUrl} onChange={(value) => setConfigForm({ ...configForm, baseUrl: value })} />
          <Input label="API Key" type="password" value={configForm.apiKey || ""} onChange={(value) => setConfigForm({ ...configForm, apiKey: value })} placeholder={editingConfigId ? "留空则不修改" : ""} />
          <Input label="Model" value={configForm.model} onChange={(value) => setConfigForm({ ...configForm, model: value })} />
          <Input label="Endpoint" value={configForm.endpoint} onChange={(value) => setConfigForm({ ...configForm, endpoint: value })} />
          <Select label="API Type" value={configForm.apiType} onChange={(value) => setConfigForm({ ...configForm, apiType: value })} options={[["openai_images_edits", "OpenAI Images Edits"], ["openai_images_generations", "OpenAI Images Generations"], ["ark_images_generations", "Ark Images Generations"]]} />
          <div className="flex items-end gap-2">
            <button type="button" onClick={saveConfig} className="h-9 flex-1 rounded-lg bg-[#007AFF] px-3 text-[13px] font-medium text-white">{editingConfigId ? "更新配置" : "新增配置"}</button>
            {editingConfigId && <button type="button" onClick={() => { setEditingConfigId(""); setConfigForm(EMPTY_CONFIG); }} className="h-9 rounded-lg bg-[#F2F2F7] px-3 text-[13px]">取消</button>}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {configs.map((config) => (
            <button key={config.id} type="button" onClick={() => editConfig(config)} className="rounded-full bg-[#F2F2F7] px-3 py-1 text-[12px] text-[#3C3C43]">{config.name || "未命名"}{config.enabled ? "" : "（停用）"}</button>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <UploadBox title="线稿图" file={lineArt} onPick={(file) => setLineArt(file)} required />
        <UploadBox title="参考款式图" file={styleReference} onPick={(file) => setStyleReference(file)} required />
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <div>
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">个人素材库</h2>
            <p className="mt-1 text-[12px] text-[#8E8E93]">常用配件永久保存；本次专用配件在下方临时上传。</p>
          </div>
          <div className="flex-1" />
          <select value={category} onChange={(event) => setCategory(event.target.value)} className="rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[13px]">
            <option value="">全部分类</option>
            {RENDER_CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <input value={search} onChange={(event) => setSearch(event.target.value)} onBlur={refreshAssets} placeholder="搜索素材" className="rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" />
          <label className="cursor-pointer rounded-lg bg-[#007AFF] px-3 py-2 text-[13px] font-medium text-white">
            上传素材
            <input type="file" accept="image/*" onChange={uploadAsset} className="hidden" />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          {filteredAssets.map((asset) => (
            <div key={asset.id} className={`rounded-xl border p-2 ${selectedAssetIds.includes(asset.id) ? "border-[#007AFF] bg-[#007AFF]/5" : "border-[#E5E5EA]"}`}>
              <button type="button" onClick={() => setSelectedAssetIds((current) => current.includes(asset.id) ? current.filter((id) => id !== asset.id) : [...current, asset.id])} className="block w-full">
                <div className="aspect-square rounded-lg bg-[#F2F2F7]"><img src={asset.thumbnailUrl || asset.url} alt={asset.name} className="h-full w-full object-contain" /></div>
                <p className="mt-2 truncate text-left text-[12px] font-medium text-[#1C1C1E]">{asset.name}</p>
                <p className="truncate text-left text-[11px] text-[#8E8E93]">{asset.category}</p>
              </button>
              <button type="button" onClick={() => removeAsset(asset.id)} className="mt-1 text-[11px] text-[#FF3B30]">删除</button>
            </div>
          ))}
          {!filteredAssets.length && <p className="col-span-full text-[13px] text-[#8E8E93]">暂无素材</p>}
        </div>
      </section>

      <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_160px_120px]">
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">提示词</span>
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" />
          </label>
          <Select label="尺寸" value={size} onChange={setSize} options={[["original", "原比例"], ["2k", "2K"], ["4k", "4K"], ["1024x1024", "1024x1024"]]} />
          <label>
            <span className="text-[12px] font-medium text-[#8E8E93]">数量</span>
            <input type="number" min={1} max={4} value={count} onChange={(event) => setCount(clampCount(event.target.value))} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="cursor-pointer rounded-lg bg-[#F2F2F7] px-3 py-2 text-[13px] font-medium">
            临时上传本次配件
            <input type="file" accept="image/*" multiple onChange={(event) => setTempAssets(Array.from(event.target.files || []))} className="hidden" />
          </label>
          <span className="text-[12px] text-[#8E8E93]">已选素材 {selectedAssetIds.length} 个，临时配件 {tempAssets.length} 个</span>
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
            {(activeTask?.images || []).map((image) => (
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
              <button key={task.id} type="button" onClick={() => setActiveTask(task)} className={`block w-full rounded-lg px-3 py-2 text-left text-[12px] ${activeTask?.id === task.id ? "bg-[#007AFF]/10 text-[#007AFF]" : "bg-[#F2F2F7] text-[#3C3C43]"}`}>
                <span className="font-medium">{task.status}</span>
                <span className="ml-2">{new Date(task.createdAt).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function UploadBox({ title, file, onPick, required }: { title: string; file: File | null; onPick: (file: File | null) => void; required?: boolean }) {
  return (
    <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{title}{required ? " *" : ""}</h2>
        {file && <button type="button" onClick={() => onPick(null)} className="text-[12px] text-[#FF3B30]">清空</button>}
      </div>
      <label className="flex min-h-[240px] cursor-pointer items-center justify-center rounded-xl border border-dashed border-[#C7C7CC] bg-[#F2F2F7]">
        <input type="file" accept="image/*" onChange={(event) => onPick(event.target.files?.[0] || null)} className="hidden" />
        <span className="text-center text-[13px] text-[#8E8E93]">{file ? file.name : `点击上传${title}`}</span>
      </label>
    </section>
  );
}

function Input({ label, value, onChange, type = "text", placeholder = "" }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return <label><span className="text-[12px] font-medium text-[#8E8E93]">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="mt-1 w-full rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px]" /></label>;
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return <label><span className="text-[12px] font-medium text-[#8E8E93]">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[13px]">{options.map(([optionValue, labelText]) => <option key={optionValue} value={optionValue}>{labelText}</option>)}</select></label>;
}

function clampCount(value: unknown): number {
  const parsed = Number.parseInt(String(value ?? 1), 10);
  if (Number.isNaN(parsed)) return 1;
  return Math.min(Math.max(parsed, 1), 4);
}
