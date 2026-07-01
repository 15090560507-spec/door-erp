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
  formData.append("count", "1");
  formData.append("selectedAssetIds", JSON.stringify(input.selectedAssetIds || []));
  formData.append("lineArt", input.lineArt);
  if (input.styleReference) formData.append("styleReference", input.styleReference);
  input.tempAssets.forEach((file) => formData.append("tempAssets", file));
  try {
    const { data } = await api.post<{ task: RenderTask }>("/render/tasks", formData, { timeout: 600000 });
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
    response?: { status?: number; data?: unknown };
  };
  const parsed = extractRenderErrorPayload(err.response?.data);
  let message = parsed.message || err.userMessage || err.message || "效果渲染请求失败";
  if (/^Request failed with status code \d+$/i.test(message) && err.response?.status) {
    message = `效果渲染请求失败，状态码 ${err.response.status}`;
  }
  const next = new Error(message) as Error & { userMessage?: string; task?: RenderTask; raw?: string };
  next.userMessage = message;
  next.task = parsed.task;
  next.raw = parsed.raw;
  return next;
}

function extractRenderErrorPayload(data: unknown): { message: string; task?: RenderTask; raw?: string } {
  if (!data) return { message: "" };
  if (typeof data === "string") return { message: cleanupErrorText(data) };
  if (Array.isArray(data)) {
    return { message: data.map((item) => extractRenderErrorPayload(item).message).filter(Boolean).join("; ") };
  }
  if (typeof data !== "object") return { message: "" };

  const record = data as Record<string, unknown>;
  const nested = record.detail ? extractRenderErrorPayload(record.detail) : { message: "" };
  const task = record.task && typeof record.task === "object" ? record.task as RenderTask : nested.task;
  const raw =
    typeof record.raw === "string" ? record.raw :
    typeof record.upstreamRawError === "string" ? record.upstreamRawError :
    nested.raw;
  const direct = firstString(record.message, record.errorMessage, record.error, record.reason);
  const message = direct || nested.message || fallbackObjectMessage(record);
  return { message: cleanupErrorText(message), task, raw };
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "";
}

function fallbackObjectMessage(record: Record<string, unknown>): string {
  try {
    const text = JSON.stringify(record);
    return text === "{}" ? "" : text;
  } catch {
    return "";
  }
}

function cleanupErrorText(text: string): string {
  const value = (text || "").trim();
  if (!value) return "";
  if (/^\s*<!doctype html/i.test(value) || /^\s*<html/i.test(value)) {
    const title = value.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.replace(/\s+/g, " ").trim();
    return title ? `上游返回 HTML 页面：${title}` : "上游返回 HTML 页面，不是图片接口 JSON";
  }
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}
