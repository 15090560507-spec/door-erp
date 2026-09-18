import { api } from "./api";

export const RENDER_CATEGORIES = ["门扇", "门框", "款式", "花件", "拉手", "锁具", "合页", "颜色", "纹理", "玻璃", "门头", "包套", "其他"];
export type RenderMode = "quick" | "precise";
export type RenderReferenceRole = "panel" | "trim" | "frame" | "glass" | "hardware";

export interface RenderReferenceBinding {
  assetIds: string[];
  files?: Array<{ id?: string; url?: string; originalName?: string; targetRole?: string }>;
}

export type RenderReferenceBindings = Record<RenderReferenceRole, RenderReferenceBinding>;

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

export interface RenderGeometryIssue {
  code: string;
  role: string;
  layer?: string;
  message: string;
}

export interface RenderGeometryValidation {
  valid: boolean;
  errors: RenderGeometryIssue[];
  warnings: RenderGeometryIssue[];
}

export interface RenderGeometryManifest {
  units: "mm" | string;
  transform_id?: string;
  canvas?: { width: number; height: number };
  roles?: Record<string, unknown>;
}

export interface RenderTask {
  id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  modelConfigId: string;
  modelConfigSnapshot?: {
    name?: string;
    provider?: string;
    baseUrl?: string;
    model?: string;
    endpoint?: string;
    apiType?: string;
  };
  prompt: string;
  size: string;
  count: number;
  files: unknown[];
  selectedAssetIds: string[];
  renderMode: RenderMode;
  sourceType: "task" | "dxf" | "image";
  sourceSide: "front" | "back";
  sourceTaskId?: string;
  referenceBindings: Partial<RenderReferenceBindings>;
  segmentation?: Record<string, unknown>;
  componentLayers?: Record<string, unknown>;
  geometryManifest?: RenderGeometryManifest | null;
  geometryValidation?: RenderGeometryValidation | null;
  compositeImage?: RenderResultImage | null;
  psdStatus?: "not_requested" | "generating" | "completed" | "failed" | string;
  psdFile?: { url?: string; originalName?: string } | null;
  images: RenderResultImage[];
  errorType: string;
  errorMessage: string;
  upstreamRawError: string;
  createdAt: string;
  startedAt: string;
  finishedAt: string;
}

export interface LineArtCropBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LineArtView {
  url: string;
  filePath?: string;
  crop?: LineArtCropBox;
}

export interface LineArtExtraction {
  id: string;
  sourceType?: "task" | "upload" | "dxf";
  taskId?: string;
  sourceUrl?: string;
  sourceWidth?: number;
  sourceHeight?: number;
  rotation?: number;
  front: LineArtView;
  back: LineArtView;
  reviewRequired: boolean;
  warnings: string[];
}

export interface RenderSegmentationFile {
  url: string;
  filePath?: string;
  originalName?: string;
  width?: number;
  height?: number;
}

export interface RenderSegmentation {
  id: string;
  source: RenderSegmentationFile;
  masks: Record<RenderReferenceRole, RenderSegmentationFile>;
  overlay: RenderSegmentationFile;
  confidence: number;
  confirmed: boolean;
  warnings: string[];
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

export async function listRenderModelConfigs(includeDisabled = true, signal?: AbortSignal): Promise<RenderModelConfig[]> {
  const { data } = await api.get<{ configs: RenderModelConfig[] }>("/render/model-configs", { params: { includeDisabled }, signal });
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

export async function deleteRenderModelConfig(id: string): Promise<void> {
  await api.delete(`/render/model-configs/${id}`);
}

export async function listRenderAssets(params?: { category?: string; q?: string; favorite?: boolean; limit?: number; offset?: number }, signal?: AbortSignal): Promise<RenderAsset[]> {
  const { data } = await api.get<{ assets: RenderAsset[] }>("/render/assets", { params, signal });
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
  renderMode?: RenderMode;
  sourceType?: "task" | "dxf" | "image";
  sourceSide?: "front" | "back";
  sourceTaskId?: string;
  referenceBindings?: Partial<RenderReferenceBindings>;
  referenceFiles?: Partial<Record<RenderReferenceRole, File[]>>;
  segmentationId?: string;
  sourceDxf?: File | null;
}): Promise<RenderTask> {
  const formData = new FormData();
  formData.append("modelConfigId", input.modelConfigId);
  formData.append("prompt", input.prompt);
  formData.append("size", input.size || "original");
  formData.append("count", "1");
  formData.append("selectedAssetIds", JSON.stringify(input.selectedAssetIds || []));
  formData.append("renderMode", input.renderMode || "quick");
  formData.append("sourceType", input.sourceType || "image");
  formData.append("sourceSide", input.sourceSide || "front");
  formData.append("sourceTaskId", input.sourceTaskId || "");
  formData.append("referenceBindings", JSON.stringify(input.referenceBindings || {}));
  formData.append("segmentationId", input.segmentationId || "");
  formData.append("lineArt", input.lineArt);
  if (input.styleReference) formData.append("styleReference", input.styleReference);
  if (input.sourceDxf) formData.append("sourceDxf", input.sourceDxf);
  input.tempAssets.forEach((file) => formData.append("tempAssets", file));
  const fieldByRole: Record<RenderReferenceRole, string> = {
    panel: "panelReferences",
    trim: "trimReferences",
    frame: "frameReferences",
    glass: "glassReferences",
    hardware: "hardwareReferences",
  };
  (Object.keys(fieldByRole) as RenderReferenceRole[]).forEach((role) => {
    (input.referenceFiles?.[role] || []).forEach((file) => formData.append(fieldByRole[role], file));
  });
  try {
    const { data } = await api.post<{ task: RenderTask }>("/render/tasks", formData, { timeout: 30000 });
    return data.task;
  } catch (error: unknown) {
    throw normalizeRenderError(error);
  }
}

export async function createRenderSegmentation(lineArt: File): Promise<RenderSegmentation> {
  const formData = new FormData();
  formData.append("lineArt", lineArt);
  const { data } = await api.post<{ segmentation: RenderSegmentation }>("/render/segmentations", formData, { timeout: 120000 });
  return data.segmentation;
}

export async function confirmRenderSegmentation(
  id: string,
  masks: Partial<Record<RenderReferenceRole, Blob>>,
): Promise<RenderSegmentation> {
  const formData = new FormData();
  const fieldByRole: Record<RenderReferenceRole, string> = {
    panel: "panelMask",
    trim: "trimMask",
    frame: "frameMask",
    glass: "glassMask",
    hardware: "hardwareMask",
  };
  (Object.keys(fieldByRole) as RenderReferenceRole[]).forEach((role) => {
    const blob = masks[role];
    if (blob) formData.append(fieldByRole[role], blob, `${role}-mask.png`);
  });
  const { data } = await api.put<{ segmentation: RenderSegmentation }>(`/render/segmentations/${id}`, formData, { timeout: 120000 });
  return data.segmentation;
}

export async function listRenderTasks(limit = 30, signal?: AbortSignal): Promise<RenderTask[]> {
  const { data } = await api.get<{ tasks: RenderTask[] }>("/render/tasks", { params: { limit }, signal });
  return data.tasks || [];
}

export async function deleteRenderTask(id: string): Promise<void> {
  await api.delete(`/render/tasks/${id}`);
}

export async function regenerateRenderComponent(id: string, role: RenderReferenceRole): Promise<RenderTask> {
  const { data } = await api.post<{ task: RenderTask }>(`/render/tasks/${id}/components/${role}/regenerate`);
  return data.task;
}

export async function generateRenderTaskPsd(id: string): Promise<RenderTask> {
  const { data } = await api.post<{ task: RenderTask }>(`/render/tasks/${id}/psd`, undefined, { timeout: 120000 });
  return data.task;
}

export async function extractUploadedLineArt(file: File): Promise<LineArtExtraction> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<{ extraction: LineArtExtraction }>("/render/line-art/extractions", formData, { timeout: 120000 });
  return { ...data.extraction, sourceType: "upload" };
}

export async function extractDxfLineArt(file: File): Promise<LineArtExtraction> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post<{ extraction: LineArtExtraction }>("/render/line-art/dxf", formData, { timeout: 120000 });
  return { ...data.extraction, sourceType: "dxf" };
}

export async function updateLineArtCrop(
  id: string,
  input: { front: LineArtCropBox; back: LineArtCropBox; rotation: number },
): Promise<LineArtExtraction> {
  const { data } = await api.put<{ extraction: LineArtExtraction }>(`/render/line-art/extractions/${id}`, input, { timeout: 120000 });
  return { ...data.extraction, sourceType: "upload" };
}

export async function extractTaskLineArt(taskId: string): Promise<LineArtExtraction> {
  const { data } = await api.get<{ extraction: LineArtExtraction }>(`/render/line-art/tasks/${taskId}`, { timeout: 120000 });
  return data.extraction;
}

export async function lineArtViewToFile(view: LineArtView, filename: string): Promise<File> {
  const requestPath = view.url.startsWith("/api/") ? view.url.slice(4) : view.url;
  const { data } = await api.get<Blob>(requestPath, { responseType: "blob", timeout: 120000 });
  return new File([data], filename, { type: data.type || "image/png" });
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
