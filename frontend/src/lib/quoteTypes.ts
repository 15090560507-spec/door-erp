// ===================== 配件 =====================
export interface Accessory {
  id: number;
  name: string;
  category: string;
  model: string;
  keywords: string;
  unit: string;
  unitPrice: number;
  remark: string;
  active: number;
}

export interface AccessoryCreate {
  name: string;
  category?: string;
  model?: string;
  keywords?: string;
  unit?: string;
  unitPrice?: number;
  remark?: string;
}

// ===================== 报价单 =====================
export interface QuoteItem {
  accessoryId: number | null;
  productName: string;
  width: number | null;
  height: number | null;
  openDirection: string;
  unit: string;
  unitPrice: number;
}

export interface QuoteFormData {
  customerName: string;
  projectName: string;
  quoteDate: string;
  noticeText: string;
  items: QuoteItem[];
}

export interface QuoteItemResponse {
  id: number;
  accessoryId: number | null;
  productName: string;
  width: number | null;
  height: number | null;
  openDirection: string;
  unit: string;
  unitPrice: number;
  rowOrder: number;
}

export interface QuoteResponse {
  id: number;
  customerName: string;
  projectName: string;
  quoteDate: string;
  noticeText: string;
  createdAt: string;
  items: QuoteItemResponse[];
}

export interface QuoteListResponse {
  quotes: QuoteResponse[];
  total: number;
}

// ===================== AI 配置 =====================
export interface AiConfig {
  baseUrl: string;
  endpointPath: string;
  apiKey: string;
  model: string;
  prompt: string;
  updatedAt: string;
}

// ===================== AI 图纸识别 =====================
export interface AnalysisItem {
  productName: string;
  width: number | null;
  height: number | null;
  openDirection: string;
  unit: string;
  unitPrice: number | null;
}

export interface AnalysisResult {
  customerName: string;
  projectName: string;
  outerWidth: number | null;
  outerHeight: number | null;
  openDirection: string;
  items: AnalysisItem[];
  accessories: string[];
  notes: string;
}

export interface DrawingAnalysisResponse {
  uploadId: number;
  filename: string;
  analysis: AnalysisResult;
  rawPreview: string;
}

// ===================== 常量 =====================
export const DEFAULT_QUOTE_NOTICE_TEXT = "本报价不含税工厂结算价，含木箱。";

export const OPEN_DIRECTION_MAP: Record<string, string> = {
  "内开": "内右开",
  "外开": "外右开",
  "右开": "内右开",
  "左开": "内左开",
  "内右": "内右开",
  "内左": "内左开",
  "外右": "外右开",
  "外左": "外左开",
};

export function normalizeOpenDirection(dir: string): string {
  if (!dir) return "";
  const d = dir.trim();
  if (!d) return "";
  if (/^(内|外)(左|右)开$/.test(d)) return d;
  return OPEN_DIRECTION_MAP[d] || d;
}

export function createEmptyQuoteItem(): QuoteItem {
  return {
    accessoryId: null,
    productName: "",
    width: null,
    height: null,
    openDirection: "",
    unit: "",
    unitPrice: 0,
  };
}

export const UNIT_OPTIONS = ["m²", "付", "套", "个", "组", "樘", "把", "支", "块", "条", "根", "台"];
