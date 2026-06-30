import { api } from "./api";

export interface RenderImageResult {
  type: "b64_json" | "url";
  src: string;
}

export interface RenderGenerateResult {
  images: RenderImageResult[];
  rawCount: number;
}

export interface RenderGenerateInput {
  lineArt: File;
  references: { label: string; file: File }[];
  baseUrl: string;
  apiKey: string;
  model: string;
  prompt: string;
  size: string;
  count: number;
}

export async function generateRender(input: RenderGenerateInput): Promise<RenderGenerateResult> {
  const formData = new FormData();
  formData.append("lineArt", input.lineArt);
  input.references.forEach((item) => {
    formData.append("reference", item.file);
  });
  formData.append("referenceLabels", JSON.stringify(input.references.map((item) => item.label.trim())));
  formData.append("baseUrl", input.baseUrl.trim());
  formData.append("apiKey", input.apiKey.trim());
  formData.append("model", input.model.trim());
  formData.append("prompt", input.prompt.trim());
  formData.append("size", input.size || "original");
  formData.append("count", String(input.count || 1));

  try {
    const { data } = await api.post<RenderGenerateResult>("/render/generate", formData, { timeout: 180000 });
    return data;
  } catch (error: unknown) {
    const message = extractRenderErrorMessage(error);
    const nextError = new Error(message) as Error & { userMessage?: string };
    nextError.userMessage = message;
    throw nextError;
  }
}

function extractRenderErrorMessage(error: unknown): string {
  const err = error as {
    userMessage?: string;
    message?: string;
    response?: {
      status?: number;
      data?: unknown;
    };
  };
  const data = err.response?.data;
  const status = err.response?.status;
  const fromData = extractMessageFromData(data);
  if (fromData) return fromData;
  if (err.userMessage) return err.userMessage;
  if (status) return `效果渲染请求失败，状态码 ${status}。请检查后端日志或上游图片接口配置。`;
  return err.message || "效果渲染请求失败";
}

function extractMessageFromData(data: unknown): string {
  if (!data) return "";
  if (typeof data === "string") return cleanupErrorText(data);
  if (typeof data !== "object") return "";
  const record = data as Record<string, unknown>;
  for (const key of ["detail", "details", "error", "message"]) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return cleanupErrorText(value);
    if (value && typeof value === "object") {
      const nested = extractMessageFromData(value);
      if (nested) return nested;
    }
  }
  return "";
}

function cleanupErrorText(text: string): string {
  const stripped = text
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return stripped.length > 500 ? `${stripped.slice(0, 500)}...` : stripped;
}
