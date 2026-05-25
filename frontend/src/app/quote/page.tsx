"use client";

import { useState, useCallback } from "react";
import type { Accessory, QuoteItem, AnalysisResult, QuoteResponse } from "@/lib/quoteTypes";
import { createEmptyQuoteItem, DEFAULT_QUOTE_NOTICE_TEXT, normalizeOpenDirection } from "@/lib/quoteTypes";
import { createQuote, getAccessories } from "@/lib/quoteApi";
import QuoteItemsTable from "@/components/QuoteItemsTable";
import QuotePreview from "@/components/QuotePreview";
import AccessoryModal from "@/components/AccessoryModal";
import AiConfigModal from "@/components/AiConfigModal";
import AiAnalysisPanel from "@/components/AiAnalysisPanel";
import QuoteHistoryModal from "@/components/QuoteHistoryModal";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
const QUOTE_ROW_COUNT = 8;

function chooseAccessoryMatch(name: string, matches: Accessory[]): Accessory | null {
  const query = name.trim();
  if (!query || !matches.length) return null;
  return (
    matches.find((item) => item.name.trim() === query) ||
    matches.find((item) => item.name.includes(query) || query.includes(item.name.trim())) ||
    matches[0]
  );
}

async function resolveAiAccessoryRows(accessories: string[]): Promise<{
  rows: QuoteItem[];
  matchedCount: number;
  lookupFailedCount: number;
}> {
  const names = accessories.map((item) => String(item || "").trim()).filter(Boolean);
  const lookups = await Promise.all(
    names.map(async (name) => {
      try {
        const matches = await getAccessories(name);
        return { name, match: chooseAccessoryMatch(name, matches), failed: false };
      } catch (error) {
        console.warn("AI accessory lookup failed:", name, error);
        return { name, match: null, failed: true };
      }
    })
  );

  let matchedCount = 0;
  let lookupFailedCount = 0;
  const rows = lookups.map(({ name, match, failed }) => {
    if (failed) lookupFailedCount += 1;
    if (match) {
      matchedCount += 1;
      return {
        ...createEmptyQuoteItem(),
        accessoryId: match.id,
        productName: match.name,
        unit: match.unit || "",
        unitPrice: match.unitPrice ?? 0,
      };
    }
    return {
      ...createEmptyQuoteItem(),
      productName: name,
      unit: "",
      unitPrice: 0,
    };
  });

  return { rows, matchedCount, lookupFailedCount };
}

export default function QuotePage() {
  // Form state
  const [customerName, setCustomerName] = useState("");
  const [projectName, setProjectName] = useState("");
  const [quoteDate, setQuoteDate] = useState(new Date().toISOString().slice(0, 10));
  const [noticeText, setNoticeText] = useState(DEFAULT_QUOTE_NOTICE_TEXT);
  const [items, setItems] = useState<QuoteItem[]>(Array.from({ length: QUOTE_ROW_COUNT }, () => createEmptyQuoteItem()));

  // Modal state
  const [accessoryOpen, setAccessoryOpen] = useState(false);
  const [aiConfigOpen, setAiConfigOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  // Status
  const [status, setStatus] = useState("");
  const [lastQuoteId, setLastQuoteId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportingType, setExportingType] = useState("");

  // Collect form data
  const collectForm = useCallback((): { customerName: string; projectName: string; quoteDate: string; noticeText: string; items: QuoteItem[] } => {
    return {
      customerName: customerName.trim(),
      projectName: projectName.trim(),
      quoteDate,
      noticeText: noticeText.trim() || DEFAULT_QUOTE_NOTICE_TEXT,
      items: items.filter((item) => item.productName.trim()),
    };
  }, [customerName, projectName, quoteDate, noticeText, items]);

  // Save quote
  async function handleSave() {
    const form = collectForm();
    if (!form.customerName) { setStatus("请填写客户名称"); return; }
    if (!form.projectName) { setStatus("请填写项目名称"); return; }
    if (!form.quoteDate) { setStatus("请选择日期"); return; }
    if (!form.items.length) { setStatus("至少填写一条品名型号"); return; }

    setSaving(true);
    setStatus("");
    try {
      const quote = await createQuote(form);
      setLastQuoteId(quote.id);
      setStatus(`已保存 #${quote.id}`);
    } catch (err: unknown) {
      const error = err as { userMessage?: string; message?: string };
      setStatus(error?.userMessage || error?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  // Export Excel: fetch blob then trigger download
  async function handleExportExcel() {
    if (!lastQuoteId) { setStatus("请先保存报价单"); return; }
    setExporting(true);
    setExportingType("xlsx");
    try {
      const res = await fetch(`${API_BASE}/quotes/${lastQuoteId}/export.xlsx`);
      if (!res.ok) throw new Error("导出失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `报价单_${lastQuoteId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus("Excel 下载中...");
    } catch {
      setStatus("Excel 导出失败");
    } finally {
      setExporting(false);
    setExportingType("");
    }
  }

  // Export JPG: 服务端渲染 Excel A1:J24 → JPG + 40px 白边
  async function handleExportJpg() {
    if (!lastQuoteId) { setStatus("请先保存报价单"); return; }
    setExporting(true);
    setExportingType("jpg");
    setStatus("正在生成 JPG...");
    try {
      const res = await fetch(`${API_BASE}/quotes/${lastQuoteId}/export.jpg`);
      if (!res.ok) throw new Error("导出失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `报价单_${lastQuoteId}.jpg`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus("JPG 已下载");
    } catch {
      setStatus("JPG 导出失败");
    } finally {
      setExporting(false);
      setExportingType("");
    }
  }

  // Print: open PDF endpoint in new window (backend returns HTML with auto-print)
  function handlePrint() {
    if (!lastQuoteId) { setStatus("请先保存报价单"); return; }
    window.open(`${API_BASE}/quotes/${lastQuoteId}/export.pdf`, "_blank");
  }

  // Apply AI analysis results
  async function handleApplyAnalysis(result: AnalysisResult) {
    if (result.customerName) setCustomerName(result.customerName);
    if (result.projectName) setProjectName(result.projectName);

    const globalDir = normalizeOpenDirection(result.openDirection);
    const fallbackWidth = result.outerWidth ?? null;
    const fallbackHeight = result.outerHeight ?? null;
    const mainItem = result.items?.[0] || null;
    const rawDir = mainItem?.openDirection || globalDir || "";
    const mainRow: QuoteItem = mainItem
      ? {
          accessoryId: null,
          productName: mainItem.productName || "",
          width: mainItem.width ?? fallbackWidth,
          height: mainItem.height ?? fallbackHeight,
          openDirection: normalizeOpenDirection(rawDir),
          unit: mainItem.unit || "m2",
          unitPrice: mainItem.unitPrice ?? 0,
        }
      : {
          ...createEmptyQuoteItem(),
          width: fallbackWidth,
          height: fallbackHeight,
          openDirection: globalDir,
        };

    let accessoryRows: QuoteItem[] = [];
    let matchedCount = 0;
    let lookupFailedCount = 0;
    try {
      const resolved = await resolveAiAccessoryRows(result.accessories || []);
      accessoryRows = resolved.rows;
      matchedCount = resolved.matchedCount;
      lookupFailedCount = resolved.lookupFailedCount;
    } catch (error) {
      console.warn("AI accessories mapping failed:", error);
      accessoryRows = (result.accessories || [])
        .map((name) => String(name || "").trim())
        .filter(Boolean)
        .map((name) => ({
          ...createEmptyQuoteItem(),
          productName: name,
        }));
      lookupFailedCount = accessoryRows.length;
    }

    const rows = [mainRow, ...accessoryRows].slice(0, QUOTE_ROW_COUNT);
    while (rows.length < QUOTE_ROW_COUNT) rows.push(createEmptyQuoteItem());
    setItems(rows);

    const overflowCount = Math.max(0, accessoryRows.length - (QUOTE_ROW_COUNT - 1));
    const statusParts = ["AI 识别结果已回填"];
    if (result.accessories?.length) statusParts.push(`配件匹配 ${matchedCount}/${result.accessories.length}`);
    if (lookupFailedCount) statusParts.push(`${lookupFailedCount} 个配件查库失败已按原名填入`);
    if (overflowCount) statusParts.push(`超过模板行数的 ${overflowCount} 个配件未回填`);
    setStatus(statusParts.join("，"));
  }

  // Load quote from history
  function handleLoadQuote(quote: QuoteResponse) {
    setCustomerName(quote.customerName);
    setProjectName(quote.projectName);
    setQuoteDate(quote.quoteDate);
    setNoticeText(quote.noticeText || DEFAULT_QUOTE_NOTICE_TEXT);
    setItems(
      Array.from({ length: QUOTE_ROW_COUNT }, (_, index) => {
        const item = quote.items?.[index];
        return item
          ? {
              accessoryId: item.accessoryId,
              productName: item.productName || "",
              width: item.width ?? null,
              height: item.height ?? null,
              openDirection: item.openDirection || "",
              unit: item.unit || "m2",
              unitPrice: item.unitPrice ?? 0,
            }
          : createEmptyQuoteItem();
      })
    );
    setLastQuoteId(quote.id);
    setStatus(`已载入报价单 #${quote.id}`);
  }

  function handleClear() {
    setCustomerName("");
    setProjectName("");
    setQuoteDate(new Date().toISOString().slice(0, 10));
    setNoticeText(DEFAULT_QUOTE_NOTICE_TEXT);
    setItems(Array.from({ length: QUOTE_ROW_COUNT }, () => createEmptyQuoteItem()));
    setLastQuoteId(null);
    setStatus("表单已清空");
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={() => setAccessoryOpen(true)}
            className="px-3.5 py-1.5 text-[13px] font-medium rounded-lg bg-white border border-[#E5E5EA]/60 text-[#1C1C1E] hover:bg-[#F2F2F7] transition-colors"
          >
            配件库
          </button>
          <button
            onClick={() => setAiConfigOpen(true)}
            className="px-3.5 py-1.5 text-[13px] font-medium rounded-lg bg-white border border-[#E5E5EA]/60 text-[#1C1C1E] hover:bg-[#F2F2F7] transition-colors"
          >
            AI 模型配置
          </button>
          <button
            onClick={() => setHistoryOpen(true)}
            className="px-3.5 py-1.5 text-[13px] font-medium rounded-lg bg-white border border-[#E5E5EA]/60 text-[#1C1C1E] hover:bg-[#F2F2F7] transition-colors"
          >
            最近报价
          </button>
          <button
            onClick={handleClear}
            className="px-3.5 py-1.5 text-[12px] font-medium rounded-lg bg-[#F2F2F7] text-[#8E8E93] hover:text-[#1C1C1E] hover:bg-[#E5E5EA]/60 transition-colors"
          >
            清空
          </button>
        </div>
        {status && (
          <span className={`text-[12px] px-3 py-1 rounded-full font-medium ${
            status.includes("失败") ? "bg-[#FF3B30]/10 text-[#FF3B30]" :
            status.includes("载入") ? "bg-[#007AFF]/10 text-[#007AFF]" :
            "bg-[#34C759]/10 text-[#34C759]"
          }`}>
            {status}
          </span>
        )}
      </div>

      {/* Main two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Editor */}
        <div className="space-y-4">
          {/* Quote Form Header */}
          <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6">
            <h2 className="text-[15px] font-semibold text-[#1C1C1E] mb-4">报价明细</h2>

            {/* Customer/Project/Date fields */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <label className="block">
                <span className="text-[12px] font-medium text-[#8E8E93]">客户名称</span>
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="客户A"
                  className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
                />
              </label>
              <label className="block">
                <span className="text-[12px] font-medium text-[#8E8E93]">项目名称</span>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="项目A"
                  className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
                />
              </label>
              <label className="block">
                <span className="text-[12px] font-medium text-[#8E8E93]">日期</span>
                <input
                  type="date"
                  value={quoteDate}
                  onChange={(e) => setQuoteDate(e.target.value)}
                  className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
                />
              </label>
            </div>
            <label className="block mb-4">
              <span className="text-[12px] font-medium text-[#8E8E93]">报价说明</span>
              <input
                type="text"
                value={noticeText}
                onChange={(e) => setNoticeText(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
              />
            </label>

            {/* Items Table */}
            <QuoteItemsTable items={items} onChange={setItems} />
          </div>

          {/* AI Analysis */}
          <AiAnalysisPanel onApply={handleApplyAnalysis} />
        </div>

        {/* Right: Preview */}
        <div className="space-y-4">
          <QuotePreview
            customerName={customerName}
            projectName={projectName}
            quoteDate={quoteDate}
            noticeText={noticeText}
            items={items}
          />

          {/* Action Buttons */}
          <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4">
            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/60 active:scale-[0.97] disabled:opacity-50 transition-all"
              >
                {saving ? "保存中..." : "保存"}
              </button>
              <button
                onClick={handleExportExcel}
                disabled={exporting}
                className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 active:scale-[0.97] disabled:opacity-60 transition-all"
              >
                {exportingType === "xlsx" ? "导出中..." : "导出 Excel"}
              </button>
              <button
                onClick={handleExportJpg}
                disabled={exporting}
                className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/60 active:scale-[0.97] disabled:opacity-50 transition-all"
              >
                {exportingType === "jpg" ? "生成中..." : "导出 JPG"}
              </button>
              <button
                onClick={handlePrint}
                disabled={exporting}
                className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/60 active:scale-[0.97] disabled:opacity-50 transition-all"
              >
                打印
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Modals */}
      <AccessoryModal open={accessoryOpen} onClose={() => setAccessoryOpen(false)} />
      <AiConfigModal open={aiConfigOpen} onClose={() => setAiConfigOpen(false)} />
      <QuoteHistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} onLoad={handleLoadQuote} />
    </div>
  );
}
