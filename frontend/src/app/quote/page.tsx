"use client";

import { useState, useCallback } from "react";
import type { QuoteItem, AnalysisResult, QuoteResponse } from "@/lib/quoteTypes";
import { createEmptyQuoteItem, normalizeOpenDirection } from "@/lib/quoteTypes";
import { createQuote } from "@/lib/quoteApi";
import QuoteItemsTable from "@/components/QuoteItemsTable";
import QuotePreview from "@/components/QuotePreview";
import AccessoryModal from "@/components/AccessoryModal";
import AiConfigModal from "@/components/AiConfigModal";
import AiAnalysisPanel from "@/components/AiAnalysisPanel";
import QuoteHistoryModal from "@/components/QuoteHistoryModal";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function QuotePage() {
  // Form state
  const [customerName, setCustomerName] = useState("");
  const [projectName, setProjectName] = useState("");
  const [quoteDate, setQuoteDate] = useState(new Date().toISOString().slice(0, 10));
  const [items, setItems] = useState<QuoteItem[]>(Array.from({ length: 8 }, () => createEmptyQuoteItem()));

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
  const collectForm = useCallback((): { customerName: string; projectName: string; quoteDate: string; items: QuoteItem[] } => {
    return {
      customerName: customerName.trim(),
      projectName: projectName.trim(),
      quoteDate,
      items: items.filter((item) => item.productName.trim()),
    };
  }, [customerName, projectName, quoteDate, items]);

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

  // Export JPG: capture the preview DOM element
  async function handleExportJpg() {
    if (!lastQuoteId) { setStatus("请先保存报价单"); return; }
    setExporting(true);
    setExportingType("jpg");
    setStatus("正在生成 JPG...");
    try {
      const previewEl = document.querySelector("#quote-preview-area");
      if (!previewEl) throw new Error("找不到预览区域");
      const { default: html2canvas } = await import("html2canvas");
      const canvas = await html2canvas(previewEl as HTMLElement, {
        scale: 2,
        backgroundColor: "#ffffff",
        useCORS: true,
        logging: false,
        onclone(clonedDoc) {
          // Strip modern CSS color functions (oklch, lch, lab) that html2canvas can't parse
          clonedDoc.querySelectorAll("*").forEach((el) => {
            const style = (el as HTMLElement).style;
            // Override Tailwind v4 oklch colors with standard hex fallbacks
            style.color = "";
            style.backgroundColor = "";
            style.borderColor = "";
          });
        },
      });
      canvas.toBlob((blob) => {
        if (!blob) { setStatus("JPG 生成失败"); setExporting(false); setExportingType(""); return; }
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `报价单_${lastQuoteId}.jpg`;
        a.click();
        URL.revokeObjectURL(url);
        setStatus("JPG 已下载");
        setExporting(false);
        setExportingType("");
      }, "image/jpeg", 0.92);
    } catch (e: any) {
      setStatus(`JPG 导出失败: ${e?.message || "未知错误"}`);
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
  function handleApplyAnalysis(result: AnalysisResult) {
    if (result.customerName) setCustomerName(result.customerName);
    if (result.projectName) setProjectName(result.projectName);

    const globalDir = normalizeOpenDirection(result.openDirection);

    setItems(
      Array.from({ length: 8 }, (_, index) => {
        const item = result.items?.[index];
        if (item) {
          const rawDir = item.openDirection || globalDir || "";
          return {
            accessoryId: null,
            productName: item.productName || "",
            width: item.width ?? null,
            height: item.height ?? null,
            openDirection: normalizeOpenDirection(rawDir),
            unit: item.unit || "m2",
            unitPrice: item.unitPrice ?? 0,
          };
        }
        return createEmptyQuoteItem();
      })
    );
    setStatus("AI 识别结果已回填");
  }

  // Load quote from history
  function handleLoadQuote(quote: QuoteResponse) {
    setCustomerName(quote.customerName);
    setProjectName(quote.projectName);
    setQuoteDate(quote.quoteDate);
    setItems(
      Array.from({ length: 8 }, (_, index) => {
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
    setItems(Array.from({ length: 8 }, () => createEmptyQuoteItem()));
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
