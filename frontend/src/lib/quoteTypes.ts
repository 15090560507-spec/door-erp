export interface Accessory {
  id: number;
  name: string;
  category: string;
  model: string;
  keywords: string;
  unit: string;
  unitPrice: number;
  remark: string;
  priceType?: string;
  priceMode?: string;
  frontStyle?: string;
  backStyle?: string;
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
  priceType?: string;
  priceMode?: string;
  frontStyle?: string;
  backStyle?: string;
}

export interface QuoteItem {
  /** 仅用于前端编辑器的稳定行标识，不会写入报价数据。 */
  rowId?: string;
  accessoryId: number | null;
  category?: string;
  productName: string;
  width: number | null;
  height: number | null;
  quantity?: number | null;
  openDirection: string;
  unit: string;
  unitPrice: number;
}

export type QuotePricingMode = "outerArea" | "framePlusTrim";

export interface QuoteDoorGroup {
  groupName: string;
  taskId: string;
  pricingMode: QuotePricingMode;
  trimUnitPrice: number;
  items: QuoteItem[];
}

export interface QuoteFormData {
  customerName: string;
  projectName: string;
  quoteDate: string;
  noticeText: string;
  items: QuoteItem[];
  doorGroups: QuoteDoorGroup[];
}

export interface QuoteItemResponse {
  id: number;
  accessoryId: number | null;
  category?: string;
  productName: string;
  width: number | null;
  height: number | null;
  quantity?: number | null;
  openDirection: string;
  unit: string;
  unitPrice: number;
  rowOrder: number;
}

export interface QuoteDoorGroupResponse {
  groupName: string;
  taskId: string;
  pricingMode: QuotePricingMode;
  trimUnitPrice: number;
  items: QuoteItemResponse[];
}

export interface QuoteResponse {
  id: number;
  customerName: string;
  projectName: string;
  quoteDate: string;
  noticeText: string;
  createdAt: string;
  items: QuoteItemResponse[];
  doorGroups?: QuoteDoorGroupResponse[];
  doorSummary?: string;
  doorWidth?: number | null;
  doorHeight?: number | null;
  doorCount?: number;
}

export interface QuoteListResponse {
  quotes: QuoteResponse[];
  total: number;
}

export interface AiConfig {
  baseUrl: string;
  endpointPath: string;
  apiKey?: string;
  hasApiKey: boolean;
  model: string;
  prompt: string;
  updatedAt: string;
}

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

export const DEFAULT_QUOTE_NOTICE_TEXT = "本报价不含税工厂结算价，不含木箱。";

export const OPEN_DIRECTION_MAP: Record<string, string> = {
  "内开": "右内开",
  "外开": "右外开",
  "右开": "右内开",
  "左开": "左内开",
  "内右": "右内开",
  "内左": "左内开",
  "外右": "右外开",
  "外左": "左外开",
  "右内": "右内开",
  "左内": "左内开",
  "右外": "右外开",
  "左外": "左外开",
  "右开内开": "右内开",
  "左开内开": "左内开",
  "右开外开": "右外开",
  "左开外开": "左外开",
  "内开右开": "右内开",
  "内开左开": "左内开",
  "外开右开": "右外开",
  "外开左开": "左外开",
};

export function normalizeOpenDirection(dir: string): string {
  if (!dir) return "";
  const d = dir.trim().replace(/\s+/g, "");
  if (!d) return "";
  if (/^[左右][内外]开$/.test(d)) return d;
  return OPEN_DIRECTION_MAP[d] || d;
}

export function createEmptyQuoteItem(): QuoteItem {
  return {
    rowId: `quote-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    accessoryId: null,
    category: "",
    productName: "",
    width: null,
    height: null,
    quantity: null,
    openDirection: "",
    unit: "",
    unitPrice: 0,
  };
}

export function isAreaQuoteUnit(unit: string): boolean {
  const normalized = (unit || "").toLowerCase();
  return normalized.includes("m2") || normalized.includes("㎡") || normalized.includes("m²");
}

export function quoteItemQuantityText(item: QuoteItem): string {
  if (!item.productName.trim()) return "";
  if (item.quantity !== null && item.quantity !== undefined) {
    const explicit = Number(item.quantity);
    if (Number.isFinite(explicit) && explicit > 0) {
      return isAreaQuoteUnit(item.unit) ? explicit.toFixed(4) : String(explicit);
    }
  }
  if (!isAreaQuoteUnit(item.unit)) return "1";
  const width = Number(item.width || 0);
  const height = Number(item.height || 0);
  if (!width || !height) return "";
  return (width * height * 0.000001).toFixed(4);
}

export function quoteItemAmountText(item: QuoteItem): string {
  const quantity = Number(quoteItemQuantityText(item));
  const unitPrice = Number(item.unitPrice || 0);
  const hasAnyValue = Boolean(
    item.productName.trim() ||
    item.width ||
    item.height ||
    item.openDirection.trim() ||
    item.unit.trim() ||
    item.unitPrice
  );

  if (!hasAnyValue) return "";
  if (!quantity && !unitPrice) return "0";
  if (!quantity || !Number.isFinite(unitPrice)) return "";
  return String(Math.round(quantity * unitPrice));
}

export const UNIT_OPTIONS = ["m²", "件", "套", "个", "组", "樘", "把", "支", "块", "条", "根", "台"];
