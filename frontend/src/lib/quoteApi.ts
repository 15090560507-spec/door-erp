import { api } from "./api";
import type {
  Accessory,
  QuoteFormData,
  QuoteResponse,
  QuoteListResponse,
  AiConfig,
  DrawingAnalysisResponse,
} from "./quoteTypes";
import type { QuoteItem } from "./quoteTypes";

// ===================== 配件 API =====================

export async function getAccessories(query?: string): Promise<Accessory[]> {
  const params = query ? { q: query } : {};
  const { data } = await api.get<{ accessories: Accessory[] }>("/accessories", { params });
  return data.accessories;
}

export async function createAccessory(item: {
  name: string;
  category?: string;
  model?: string;
  keywords?: string;
  unit?: string;
  unitPrice?: number;
  remark?: string;
  priceType?: string;
  priceMode?: string;
  frontStyle?: string;
  backStyle?: string;
}): Promise<{ id: number }> {
  const { data } = await api.post<{ id: number }>("/accessories", item);
  return data;
}

export async function deleteAccessory(id: number): Promise<void> {
  await api.delete(`/accessories/${id}`);
}

export async function exportAccessories(): Promise<Accessory[]> {
  const { data } = await api.get<{ accessories: Accessory[] }>("/accessories/export");
  return data.accessories;
}

export async function importAccessories(
  items: Array<{
    name: string;
    category?: string;
    model?: string;
    keywords?: string;
    unit?: string;
    unitPrice?: number;
    remark?: string;
    priceType?: string;
    priceMode?: string;
    frontStyle?: string;
    backStyle?: string;
  }>
): Promise<{ imported: number }> {
  const { data } = await api.post<{ imported: number }>("/accessories/import", { accessories: items });
  return data;
}

export async function importAccessoriesXlsx(file: File): Promise<{ imported: number; parsed: number }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<{ imported: number; parsed: number }>("/accessories/import-xlsx", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function rememberQuoteItems(items: QuoteItem[]): Promise<{ remembered: number }> {
  const { data } = await api.post<{ remembered: number }>("/accessories/remember-quote", { items });
  return data;
}

// ===================== 报价单 API =====================

export async function getQuotes(): Promise<QuoteListResponse> {
  const { data } = await api.get<QuoteListResponse>("/quotes");
  return data;
}

export async function createQuote(form: QuoteFormData): Promise<QuoteResponse> {
  const { data } = await api.post<{ quote: QuoteResponse }>("/quotes", form);
  return data.quote;
}

export async function getQuote(id: number): Promise<QuoteResponse> {
  const { data } = await api.get<{ quote: QuoteResponse }>(`/quotes/${id}`);
  return data.quote;
}

export async function deleteQuote(id: number): Promise<void> {
  await api.delete(`/quotes/${id}`);
}

// ===================== AI 配置 API =====================

export async function getAiConfig(): Promise<AiConfig> {
  const { data } = await api.get<{ config: AiConfig }>("/ai-config");
  return data.config;
}

export async function updateAiConfig(config: Partial<AiConfig>): Promise<AiConfig> {
  const { data } = await api.post<{ config: AiConfig }>("/ai-config", config);
  return data.config;
}

// ===================== 图纸分析 API =====================

export async function analyzeDrawing(file: File): Promise<DrawingAnalysisResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<DrawingAnalysisResponse>("/drawings/analyze", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
