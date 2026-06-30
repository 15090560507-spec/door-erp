import { api } from "./api";

export const RENDER_CATEGORIES = ["款式", "花件", "拉手", "锁具", "合页", "颜色", "纹理", "玻璃", "门头", "包套", "其他"];

export interface ProviderCapabilities {
  textToImage: boolean;
  imageToImage: boolean;
  imageEdit: boolean;
  singleReference: boolean;
  multiReference: boolean;
  inputBase64: boolean;
  inputUrl: boolean;
  sync: boolean;
  asyncTask: boolean;
}

export interface RenderModelConfig {
  id: string;
  name: string;
  provider: string;
  baseUrl: string;
  model: string;
  endpoint: string;
  apiType: string;
  capabilities: ProviderCapabilities;
  defaultSize: string;
  timeoutSeconds: number;
  enabled: boolean;
  hasApiKey: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface RenderAsset {
  id: string;
  name: string;
  category: string;
  url: string;
  thumbnailUrl: string;
  tags: string[];
  remark: string;
  favorite: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface RenderResultImage {
  id: string;
  type: "url" | "file" | "b64_json";
  src: string;
  filePath?: string;
}

export interface RenderTask {
  id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  modelConfigId: string;
  prompt: string;
  size: string;
  count: number;
  files: unknown[];
  selectedAssetIds: string[];
  images: RenderResultImage[];
  errorType: string;
  errorMessage: string;
  upstreamRawError: string;
  createdAt: string;
  startedAt: string;
  finishedAt: string;
}

export interface ModelConfigInput {
  name: string;
  provider: string;
  baseUrl: string;
  apiKey?: string;
  model: string;
  endpoint: string;
  apiType: string;
  defaultSize: string;
  timeoutSeconds: number;
  enabled: boolean;
}

export async function listRenderModelConfigs(includeDisabled = true): Promise<RenderModelConfig[]> {
  const { data } = await api.get<{ configs: RenderModelConfig[] }>("/render/model-configs", { params: { includeDisabled } });
  return data.configs || [];
}

export async function createRenderModelConfig(input: ModelConfigInput): Promise<RenderModelConfig> {
  const { data } = await api.post<{ config: RenderModelConfig }>("/render/model-configs", input);
  return data.config;
}

export async function updateRenderModelConfig(id: string, input: Partial<ModelConfigInput>): Promise<RenderModelConfig> {
  const { data } = await api.put<{ config: RenderModelConfig }>(`/render/model-configs/${id}`, input);
  return data.config;
}

export async function listRenderAssets(params?: { category?: string; q?: string; favorite?: boolean }): Promise<RenderAsset[]> {
  const { data } = await api.get<{ assets: RenderAsset[] }>("/render/assets", { params });
  return data.assets || [];
}

export async function uploadRenderAsset(input: {
  file: File;
  name: string;
  category: string;
  tags?: string[];
  remark?: string;
  favorite?: boolean;
}): Promise<RenderAsset> {
  const formData = new FormData();
  formData.append("file", input.file);
  formData.append("name", input.name);
  formData.append("category", input.category);
  formData.append("tags", JSON.stringify(input.tags || []));
  formData.append("remark", input.remark || "");
  formData.append("favorite", String(Boolean(input.favorite)));
  const { data } = await api.post<{ asset: RenderAsset }>("/render/assets", formData, { timeout: 120000 });
  return data.asset;
}

export async function updateRenderAsset(id: string, patch: Partial<Pick<RenderAsset, "name" | "category" | "tags" | "remark" | "favorite">>): Promise<RenderAsset> {
  const { data } = await api.put<{ asset: RenderAsset }>(`/render/assets/${id}`, patch);
  return data.asset;
}

export async function deleteRenderAsset(id: string): Promise<void> {
  await api.delete(`/render/assets/${id}`);
}

export async function createRenderTask(input: {
  modelConfigId: string;
  prompt: string;
  size: string;
  count: number;
  selectedAssetIds: string[];
  lineArt: File;
  styleReference?: File | null;
  tempAssets: File[];
}): Promise<RenderTask> {
  const formData = new FormData();
  formData.append("modelConfigId", input.modelConfigId);
  formData.append("prompt", input.prompt);
  formData.append("size", input.size || "original");
  formData.append("count", String(input.count || 1));
  formData.append("selectedAssetIds", JSON.stringify(input.selectedAssetIds || []));
  formData.append("lineArt", input.lineArt);
  if (input.styleReference) formData.append("styleReference", input.styleReference);
  input.tempAssets.forEach((file) => formData.append("tempAssets", file));
  try {
    const { data } = await api.post<{ task: RenderTask }>("/render/tasks", formData, { timeout: 240000 });
    return data.task;
  } catch (error: unknown) {
    throw normalizeRenderError(error);
  }
}

export async function listRenderTasks(limit = 30): Promise<RenderTask[]> {
  const { data } = await api.get<{ tasks: RenderTask[] }>("/render/tasks", { params: { limit } });
  return data.tasks || [];
}

function normalizeRenderError(error: unknown): Error & { userMessage?: string; task?: RenderTask; raw?: string } {
  const err = error as {
    userMessage?: string;
    message?: string;
    response?: { data?: { detail?: unknown } };
  };
  const detail = err.response?.data?.detail;
  let message = "";
  let task: RenderTask | undefined;
  let raw = "";
  if (typeof detail === "string") message = detail;
  else if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    if (record.task && typeof record.task === "object") task = record.task as RenderTask;
    if (typeof record.raw === "string") raw = record.raw;
    message = String(record.message || record.errorMessage || JSON.stringify(detail));
  }
  if (!message) message = err.userMessage || err.message || "效果渲染请求失败";
  const next = new Error(message) as Error & { userMessage?: string; task?: RenderTask; raw?: string };
  next.userMessage = message;
  next.task = task;
  next.raw = raw;
  return next;
}
