"use client";

import { useState, useCallback, useEffect } from "react";
import type { Accessory, QuoteItem, AnalysisResult, QuoteResponse } from "@/lib/quoteTypes";
import { createEmptyQuoteItem, DEFAULT_QUOTE_NOTICE_TEXT, normalizeOpenDirection } from "@/lib/quoteTypes";
import { createQuote, getAccessories } from "@/lib/quoteApi";
import { api, getTask, getTasks } from "@/lib/api";
import type { DoorFormData, TaskItem } from "@/lib/types";
import QuoteItemsTable from "@/components/QuoteItemsTable";
import QuotePreview from "@/components/QuotePreview";
import AccessoryModal from "@/components/AccessoryModal";
import AiConfigModal from "@/components/AiConfigModal";
import AiAnalysisPanel from "@/components/AiAnalysisPanel";
import QuoteHistoryModal from "@/components/QuoteHistoryModal";
import { localDateYmd } from "@/lib/dateTime";

const QUOTE_ROW_COUNT = 8;
type QuotePricingMode = "outerArea" | "framePlusTrim";

async function downloadQuoteFile(quoteId: number, ext: "xlsx" | "jpg" | "pdf", filename: string) {
  const { data } = await api.get<Blob>(`/quotes/${quoteId}/export.${ext}`, { responseType: "blob" });
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function num(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function padQuoteRows(rows: QuoteItem[]): QuoteItem[] {
  const next = rows.slice(0, QUOTE_ROW_COUNT);
  while (next.length < QUOTE_ROW_COUNT) next.push(createEmptyQuoteItem());
  return next;
}

function normalizeQuoteRows(rows: QuoteItem[]): QuoteItem[] {
  return rows.map((item, index) => index === 0 ? item : { ...item, openDirection: "" });
}

function calcAreas(params: DoorFormData) {
  const frameWidth = num(params.dw);
  const frameHeight = num(params.dh);
  const frontOuterSideWidth = params.has_outer
    ? num(params.trim_front_in)
    : params.has_outer_portal
      ? num(params.outer_portal_pillar_width)
      : 0;
  const frontOuterTopHeight = params.has_outer
    ? num(params.trim_front_in)
    : params.has_outer_portal
      ? num(params.outer_portal_header_height)
      : 0;
  const innerTrimWidth = params.has_inner ? num(params.trim_back_in) : 0;
  const outerWidth = frameWidth + (frontOuterSideWidth + innerTrimWidth) * 2;
  const outerHeight = frameHeight + frontOuterTopHeight + innerTrimWidth;
  const frameArea = frameWidth && frameHeight ? frameWidth * frameHeight * 0.000001 : 0;
  const outerArea = outerWidth && outerHeight ? outerWidth * outerHeight * 0.000001 : 0;
  const trimArea = Math.max(0, outerArea - frameArea);
  return { frameWidth, frameHeight, outerWidth, outerHeight, frameArea, outerArea, trimArea };
}

function rowFromAccessory(accessory: Accessory, productName = accessory.name, width: number | null = null, height: number | null = null, openDirection = ""): QuoteItem {
  return {
    accessoryId: accessory.id,
    productName,
    width,
    height,
    quantity: null,
    openDirection,
    unit: accessory.unit || "",
    unitPrice: accessory.unitPrice ?? 0,
  };
}

function findPriceItem(accessories: Accessory[], category: string, name?: string): Accessory | null {
  const query = String(name || "").trim();
  if (!query) return null;
  const scoped = accessories.filter((item) => item.category === category);
  return (
    scoped.find((item) => item.name.trim() === query) ||
    scoped.find((item) => item.name.includes(query) || query.includes(item.name.trim())) ||
    null
  );
}

function findStyleCombo(accessories: Accessory[], frontStyle: string, backStyle: string): Accessory | null {
  const front = frontStyle.trim();
  const back = backStyle.trim();
  if (!front || !back) return null;
  const scoped = accessories.filter((item) => item.category === "款式组合");
  return (
    scoped.find((item) => item.frontStyle === front && item.backStyle === back) ||
    scoped.find((item) => item.name.includes(front) && item.name.includes(back)) ||
    null
  );
}

function findHingePrice(accessories: Accessory[], hinge: string, doorType: string): Accessory | null {
  const query = hinge.trim();
  if (!query) return null;
  const matches = accessories.filter((item) => item.category === "合页" && (item.name.includes(query) || item.keywords?.includes(query)));
  if (!matches.length) return null;
  const needsDouble = ["对开门", "两定两开", "四开门", "折叠四开门"].some((name) => doorType.includes(name));
  return matches.find((item) => item.name.includes(needsDouble ? "对开" : "单门")) || matches[0];
}

function buildHingeQuoteRow(accessories: Accessory[], hinge: string, doorType: string, direction: string): QuoteItem | null {
  const query = hinge.trim();
  if (!query) return null;
  const needsDouble = ["对开门", "子母门", "两定两开", "四开门", "折叠四开门"].some((name) => doorType.includes(name));
  if (query.includes("暗合页")) {
    return {
      ...createEmptyQuoteItem(),
      productName: `暗合页（${needsDouble ? 6 : 3}只）`,
      openDirection: direction,
      unit: "套",
      unitPrice: needsDouble ? 1000 : 500,
    };
  }
  const hingeItem = findHingePrice(accessories, query, doorType);
  return hingeItem && num(hingeItem.unitPrice) > 0 ? rowFromAccessory(hingeItem, hingeItem.name, null, null, direction) : null;
}

function buildQuoteRowsFromTask(params: DoorFormData, accessories: Accessory[], pricingMode: QuotePricingMode, trimUnitPrice: number): QuoteItem[] {
  const direction = normalizeOpenDirection(`${params.sel_kx || ""}${params.sel_nk || ""}`);
  const { frameWidth, frameHeight, outerWidth, outerHeight, trimArea } = calcAreas(params);
  const material = findPriceItem(accessories, "制作材料", params.zzcl);
  const style = findStyleCombo(accessories, params.zmks || "", params.fmks || "");
  const lock = findPriceItem(accessories, "锁体", params.st_val);
  const packing = findPriceItem(accessories, "包装", params.sel_bz);
  const mainUnitPrice = num(style?.unitPrice) + num(material?.unitPrice) + num(lock?.unitPrice);

  const rows: QuoteItem[] = [{
    accessoryId: style?.id ?? null,
    productName: [params.zzcl, `${params.zmks || ""}+${params.fmks || ""}`].filter(Boolean).join(" "),
    width: (pricingMode === "outerArea" ? outerWidth : frameWidth) || null,
    height: (pricingMode === "outerArea" ? outerHeight : frameHeight) || null,
    quantity: null,
    openDirection: direction,
    unit: "m2",
    unitPrice: mainUnitPrice,
  }];

  if (pricingMode === "framePlusTrim" && trimArea > 0) {
    rows.push({
      accessoryId: null,
      productName: "门套面积",
      width: null,
      height: null,
      quantity: Number(trimArea.toFixed(4)),
      openDirection: direction,
      unit: "m2",
      unitPrice: trimUnitPrice,
    });
  }

  const packingRow = packing && num(packing.unitPrice) > 0
    ? rowFromAccessory(packing, `包装-${packing.name}`, outerWidth || null, outerHeight || null, direction)
    : null;

  const hingeRow = buildHingeQuoteRow(accessories, params.sel_hys || "", params.door_type || "", direction);
  if (hingeRow) rows.push(hingeRow);

  const fingerprint = findPriceItem(accessories, "配件", params.fingerprint_lock);
  if (fingerprint && params.fingerprint_lock && params.fingerprint_lock !== "无") rows.push(rowFromAccessory(fingerprint, fingerprint.name, null, null, direction));

  const handleNames = Array.from(new Set([params.zmls, params.fmls].filter((name) => name && name !== "标配拉手")));
  handleNames.forEach((handleName) => {
    const match = findPriceItem(accessories, "配件", handleName);
    if (match) rows.push(rowFromAccessory(match, match.name, null, null, direction));
  });

  if ((params.qc_shape || "").includes("弧") || (params.sel_qc || "").includes("弧")) {
    const arcWindow = findPriceItem(accessories, "配件", "圆弧气窗");
    if (arcWindow) rows.push(rowFromAccessory(arcWindow, arcWindow.name, null, null, direction));
  }

  if (packingRow) {
    if (rows.length >= QUOTE_ROW_COUNT) {
      rows[QUOTE_ROW_COUNT - 1] = packingRow;
    } else {
      rows.push(packingRow);
    }
  }

  return normalizeQuoteRows(padQuoteRows(rows));
}

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
  const [quoteDate, setQuoteDate] = useState(localDateYmd);
  const [noticeText, setNoticeText] = useState(DEFAULT_QUOTE_NOTICE_TEXT);
  const [items, setItems] = useState<QuoteItem[]>(Array.from({ length: QUOTE_ROW_COUNT }, () => createEmptyQuoteItem()));
  const [drawingTasks, setDrawingTasks] = useState<TaskItem[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [quotePricingMode, setQuotePricingMode] = useState<QuotePricingMode>("outerArea");
  const [trimUnitPrice, setTrimUnitPrice] = useState("");

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

  useEffect(() => {
    let alive = true;
    getTasks({ limit: 100, offset: 0 })
      .then((res) => {
        if (alive) setDrawingTasks(res.tasks || []);
      })
      .catch((error) => {
        console.warn("load drawing tasks failed:", error);
      });
    return () => { alive = false; };
  }, []);

  const handleItemsChange = useCallback((rows: QuoteItem[]) => {
    setItems(normalizeQuoteRows(rows));
  }, []);

  // Collect form data
  const collectForm = useCallback((): { customerName: string; projectName: string; quoteDate: string; noticeText: string; items: QuoteItem[] } => {
    return {
      customerName: customerName.trim(),
      projectName: projectName.trim(),
      quoteDate,
      noticeText: noticeText.trim() || DEFAULT_QUOTE_NOTICE_TEXT,
      items: normalizeQuoteRows(items).filter((item) => item.productName.trim()),
    };
  }, [customerName, projectName, quoteDate, noticeText, items]);

  // Save quote
  async function handleSave() {
    const form = collectForm();
    if (!form.customerName) { setStatus("请填写客户名称"); return; }
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
      await downloadQuoteFile(lastQuoteId, "xlsx", `报价单_${lastQuoteId}.xlsx`);
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
      await downloadQuoteFile(lastQuoteId, "jpg", `报价单_${lastQuoteId}.jpg`);
      setStatus("JPG 已下载");
    } catch {
      setStatus("JPG 导出失败");
    } finally {
      setExporting(false);
      setExportingType("");
    }
  }

  async function handlePrint() {
    if (!lastQuoteId) { setStatus("请先保存报价单"); return; }
    setExporting(true);
    setExportingType("pdf");
    setStatus("正在生成 PDF...");
    try {
      await downloadQuoteFile(lastQuoteId, "pdf", `报价单_${lastQuoteId}.pdf`);
      setStatus("PDF 已下载");
    } catch {
      setStatus("PDF 导出失败");
    } finally {
      setExporting(false);
      setExportingType("");
    }
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
          quantity: null,
          openDirection: normalizeOpenDirection(rawDir),
          unit: mainItem.unit || "m2",
          unitPrice: mainItem.unitPrice ?? 0,
        }
      : {
          ...createEmptyQuoteItem(),
          width: fallbackWidth,
          height: fallbackHeight,
          quantity: null,
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
    setItems(normalizeQuoteRows(rows));

    const overflowCount = Math.max(0, accessoryRows.length - (QUOTE_ROW_COUNT - 1));
    const statusParts = ["AI 识别结果已回填"];
    if (result.accessories?.length) statusParts.push(`配件匹配 ${matchedCount}/${result.accessories.length}`);
    if (lookupFailedCount) statusParts.push(`${lookupFailedCount} 个配件查库失败已按原名填入`);
    if (overflowCount) statusParts.push(`超过模板行数的 ${overflowCount} 个配件未回填`);
    setStatus(statusParts.join("，"));
  }

  async function handleApplyTaskQuote(taskId: string, mode = quotePricingMode, trimPrice = trimUnitPrice) {
    setSelectedTaskId(taskId);
    if (!taskId) return;
    setStatus("正在读取图纸项目...");
    try {
      const task = await getTask(taskId);
      const params = task.params;
      const allAccessories = await getAccessories();
      setCustomerName(params.dhdw || task.customer || "");
      setProjectName(params.gdmc || task.project || "");
      setQuoteDate((params.dhrq || localDateYmd()).replace(/\./g, "-"));
      setItems(buildQuoteRowsFromTask(params, allAccessories, mode, num(trimPrice)));
      setLastQuoteId(null);
      setStatus("已根据图纸项目生成报价明细");
    } catch (error: unknown) {
      const err = error as { userMessage?: string; message?: string };
      setStatus(err?.userMessage || err?.message || "图纸项目报价生成失败");
    }
  }

  async function handlePricingModeChange(nextMode: QuotePricingMode) {
    setQuotePricingMode(nextMode);
    if (selectedTaskId) {
      await handleApplyTaskQuote(selectedTaskId, nextMode, trimUnitPrice);
    }
  }

  async function handleTrimUnitPriceChange(value: string) {
    setTrimUnitPrice(value);
    if (selectedTaskId && quotePricingMode === "framePlusTrim") {
      try {
        const task = await getTask(selectedTaskId);
        const allAccessories = await getAccessories();
        setItems(buildQuoteRowsFromTask(task.params, allAccessories, "framePlusTrim", num(value)));
        setLastQuoteId(null);
      } catch (error: unknown) {
        const err = error as { userMessage?: string; message?: string };
        setStatus(err?.userMessage || err?.message || "门套单价更新失败");
      }
    }
  }

  // Load quote from history
  function handleLoadQuote(quote: QuoteResponse) {
    setCustomerName(quote.customerName);
    setProjectName(quote.projectName);
    setQuoteDate(quote.quoteDate);
    setNoticeText(quote.noticeText || DEFAULT_QUOTE_NOTICE_TEXT);
    setItems(normalizeQuoteRows(
      Array.from({ length: QUOTE_ROW_COUNT }, (_, index) => {
        const item = quote.items?.[index];
        return item
          ? {
              accessoryId: item.accessoryId,
              productName: item.productName || "",
              width: item.width ?? null,
              height: item.height ?? null,
              quantity: item.quantity ?? null,
              openDirection: item.openDirection || "",
              unit: item.unit || "m2",
              unitPrice: item.unitPrice ?? 0,
            }
          : createEmptyQuoteItem();
      })
    ));
    setLastQuoteId(quote.id);
    setStatus(`已载入报价单 #${quote.id}`);
  }

  function handleClear() {
    setCustomerName("");
    setProjectName("");
    setQuoteDate(localDateYmd());
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

            <label className="block mb-4">
              <span className="text-[12px] font-medium text-[#8E8E93]">关联图纸项目</span>
              <select
                value={selectedTaskId}
                onChange={(e) => handleApplyTaskQuote(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none bg-white"
              >
                <option value="">选择图纸项目后自动报价</option>
                {drawingTasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.customer || "未填客户"} / {task.project || "未填项目"} / {task.door_type || ""} / {task.size || ""}
                  </option>
                ))}
              </select>
            </label>

            <div className="mb-4 rounded-xl border border-[#E5E5EA]/60 bg-[#F8F8FA] p-3">
              <div className="mb-2 text-[12px] font-medium text-[#8E8E93]">报价模式</div>
              <div className="flex flex-wrap items-end gap-2">
                <button
                  type="button"
                  onClick={() => handlePricingModeChange("outerArea")}
                  className={`rounded-lg px-3 py-2 text-[12px] font-medium transition-colors ${
                    quotePricingMode === "outerArea" ? "bg-[#007AFF] text-white" : "bg-white text-[#1C1C1E] border border-[#E5E5EA]/60"
                  }`}
                >
                  外围面积 × 单价
                </button>
                <button
                  type="button"
                  onClick={() => handlePricingModeChange("framePlusTrim")}
                  className={`rounded-lg px-3 py-2 text-[12px] font-medium transition-colors ${
                    quotePricingMode === "framePlusTrim" ? "bg-[#007AFF] text-white" : "bg-white text-[#1C1C1E] border border-[#E5E5EA]/60"
                  }`}
                >
                  门框面积 × 单价 + 门套面积 × 单价
                </button>
                {quotePricingMode === "framePlusTrim" && (
                  <label className="min-w-[150px]">
                    <span className="block text-[12px] font-medium text-[#8E8E93]">门套单价</span>
                    <input
                      type="number"
                      step="0.01"
                      value={trimUnitPrice}
                      onChange={(e) => handleTrimUnitPriceChange(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-[#E5E5EA]/60 px-3 py-2 text-[13px] focus:border-[#007AFF] focus:outline-none"
                    />
                  </label>
                )}
              </div>
            </div>

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
              <span className="ml-2 inline-flex gap-1">
                <button
                  type="button"
                  onClick={() => setNoticeText("本报价不含税工厂结算价，含木箱。")}
                  className="rounded-md bg-[#F2F2F7] px-2 py-1 text-[11px] text-[#1C1C1E]"
                >
                  含木箱
                </button>
                <button
                  type="button"
                  onClick={() => setNoticeText("本报价不含税工厂结算价，不含木箱。")}
                  className="rounded-md bg-[#F2F2F7] px-2 py-1 text-[11px] text-[#1C1C1E]"
                >
                  不含木箱
                </button>
              </span>
              <input
                type="text"
                value={noticeText}
                onChange={(e) => setNoticeText(e.target.value)}
                className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
              />
            </label>

            {/* Items Table */}
            <QuoteItemsTable items={items} onChange={handleItemsChange} />
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
            items={normalizeQuoteRows(items)}
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
