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
  reference: File;
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
  formData.append("reference", input.reference);
  formData.append("baseUrl", input.baseUrl.trim());
  formData.append("apiKey", input.apiKey.trim());
  formData.append("model", input.model.trim());
  formData.append("prompt", input.prompt.trim());
  formData.append("size", input.size || "1k");
  formData.append("count", String(input.count || 1));

  const { data } = await api.post<RenderGenerateResult>("/render/generate", formData, { timeout: 180000 });
  return data;
}
