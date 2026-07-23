"use client";

import { useState, useCallback, useEffect } from "react";
import type {
  Accessory,
  QuoteDoorGroup,
  QuoteItem,
  QuotePricingMode,
  AnalysisResult,
  QuoteResponse,
} from "@/lib/quoteTypes";
import { createEmptyQuoteItem, DEFAULT_QUOTE_NOTICE_TEXT, normalizeOpenDirection } from "@/lib/quoteTypes";
import { createQuote, getAccessories, rememberQuoteItems } from "@/lib/quoteApi";
import { api, getTask, getTasks } from "@/lib/api";
import type { DoorFormData, TaskItem } from "@/lib/types";
import QuoteItemsTable from "@/components/QuoteItemsTable";
import QuotePreview from "@/components/QuotePreview";
import AccessoryModal from "@/components/AccessoryModal";
import AiConfigModal from "@/components/AiConfigModal";
import AiAnalysisPanel from "@/components/AiAnalysisPanel";
import QuoteHistoryModal from "@/components/QuoteHistoryModal";
import { localDateYmd } from "@/lib/dateTime";

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

function normalizeQuoteRows(rows: QuoteItem[]): QuoteItem[] {
  return rows.map((item, index) => index === 0 ? item : { ...item, openDirection: "" });
}

function createQuoteGroup(index = 0): QuoteDoorGroup {
  return {
    groupName: `第${index + 1}樘门`,
    taskId: "",
    pricingMode: "outerArea",
    trimUnitPrice: 0,
    items: [createEmptyQuoteItem()],
  };
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
    category: accessory.category || "",
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
    category: "门类组合",
    productName: [params.door_type, params.zzcl, params.zmks, params.fmks].filter(Boolean).join(" "),
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
    rows.push(packingRow);
  }

  return normalizeQuoteRows(rows);
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
  const [doorGroups, setDoorGroups] = useState<QuoteDoorGroup[]>([createQuoteGroup()]);
  const [drawingTasks, setDrawingTasks] = useState<TaskItem[]>([]);
  const [rememberQuote, setRememberQuote] = useState(false);

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

  const updateDoorGroup = useCallback((groupIndex: number, updates: Partial<QuoteDoorGroup>) => {
    setDoorGroups((groups) => groups.map((group, index) => (
      index === groupIndex ? { ...group, ...updates } : group
    )));
    setLastQuoteId(null);
  }, []);

  // Collect form data
  const collectForm = useCallback(() => {
    const cleanedGroups = doorGroups
      .map((group, index) => ({
        ...group,
        groupName: group.groupName.trim() || `第${index + 1}樘门`,
        items: normalizeQuoteRows(group.items).filter((item) => item.productName.trim()),
      }))
      .filter((group) => group.items.length > 0);
    const items = cleanedGroups.flatMap((group) => group.items);
    return {
      customerName: customerName.trim(),
      projectName: projectName.trim(),
      quoteDate,
      noticeText: noticeText.trim() || DEFAULT_QUOTE_NOTICE_TEXT,
      items,
      doorGroups: cleanedGroups,
    };
  }, [customerName, projectName, quoteDate, noticeText, doorGroups]);

  const rememberCurrentQuote = useCallback(async (items: QuoteItem[]) => {
    if (!rememberQuote) return 0;
    const result = await rememberQuoteItems(items);
    return result.remembered;
  }, [rememberQuote]);

  const tryRememberCurrentQuote = useCallback(async (items: QuoteItem[]) => {
    try {
      return { remembered: await rememberCurrentQuote(items), failed: false };
    } catch (error) {
      console.warn("remember quote items failed:", error);
      return { remembered: 0, failed: true };
    }
  }, [rememberCurrentQuote]);

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
      let remembered = 0;
      try {
        remembered = await rememberCurrentQuote(form.items);
      } catch (error) {
        console.warn("remember quote items failed:", error);
        setStatus(`已保存 #${quote.id}，但报价记忆写入失败`);
        return;
      }
      setStatus(`已保存 #${quote.id}${rememberQuote ? `，已记忆 ${remembered} 条价格` : ""}`);
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
      const memoryResult = await tryRememberCurrentQuote(collectForm().items);
      await downloadQuoteFile(lastQuoteId, "xlsx", `报价单_${lastQuoteId}.xlsx`);
      setStatus(memoryResult.failed ? "Excel 已下载，但报价记忆写入失败" : "Excel 下载中...");
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
      const memoryResult = await tryRememberCurrentQuote(collectForm().items);
      await downloadQuoteFile(lastQuoteId, "jpg", `报价单_${lastQuoteId}.jpg`);
      setStatus(memoryResult.failed ? "JPG 已下载，但报价记忆写入失败" : "JPG 已下载");
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
      const memoryResult = await tryRememberCurrentQuote(collectForm().items);
      await downloadQuoteFile(lastQuoteId, "pdf", `报价单_${lastQuoteId}.pdf`);
      setStatus(memoryResult.failed ? "PDF 已下载，但报价记忆写入失败" : "PDF 已下载");
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
          category: "门类组合",
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

    const rows = normalizeQuoteRows([mainRow, ...accessoryRows]);
    updateDoorGroup(0, { items: rows.length ? rows : [createEmptyQuoteItem()] });

    const statusParts = ["AI 识别结果已回填"];
    if (result.accessories?.length) statusParts.push(`配件匹配 ${matchedCount}/${result.accessories.length}`);
    if (lookupFailedCount) statusParts.push(`${lookupFailedCount} 个配件查库失败已按原名填入`);
    setStatus(statusParts.join("，"));
  }

  async function handleApplyTaskQuote(
    groupIndex: number,
    taskId: string,
    mode: QuotePricingMode,
    trimPrice: number,
  ) {
    updateDoorGroup(groupIndex, { taskId, pricingMode: mode, trimUnitPrice: trimPrice });
    if (!taskId) return;
    setStatus("正在读取图纸项目...");
    try {
      const task = await getTask(taskId);
      const params = task.params;
      const allAccessories = await getAccessories();
      if (!customerName.trim()) setCustomerName(params.dhdw || task.customer || "");
      if (!projectName.trim()) setProjectName(params.gdmc || task.project || "");
      if (groupIndex === 0) setQuoteDate((params.dhrq || localDateYmd()).replace(/\./g, "-"));
      updateDoorGroup(groupIndex, {
        taskId,
        pricingMode: mode,
        trimUnitPrice: trimPrice,
        items: buildQuoteRowsFromTask(params, allAccessories, mode, trimPrice),
      });
      setLastQuoteId(null);
      setStatus(`已根据图纸项目生成${groupIndex + 1}号门报价明细`);
    } catch (error: unknown) {
      const err = error as { userMessage?: string; message?: string };
      setStatus(err?.userMessage || err?.message || "图纸项目报价生成失败");
    }
  }

  async function handlePricingModeChange(groupIndex: number, nextMode: QuotePricingMode) {
    const group = doorGroups[groupIndex];
    updateDoorGroup(groupIndex, { pricingMode: nextMode });
    if (group?.taskId) {
      await handleApplyTaskQuote(groupIndex, group.taskId, nextMode, group.trimUnitPrice);
    }
  }

  async function handleTrimUnitPriceChange(groupIndex: number, value: string) {
    const price = num(value);
    const group = doorGroups[groupIndex];
    updateDoorGroup(groupIndex, { trimUnitPrice: price });
    if (group?.taskId && group.pricingMode === "framePlusTrim") {
      try {
        const task = await getTask(group.taskId);
        const allAccessories = await getAccessories();
        updateDoorGroup(groupIndex, {
          items: buildQuoteRowsFromTask(task.params, allAccessories, "framePlusTrim", price),
        });
        setLastQuoteId(null);
      } catch (error: unknown) {
        const err = error as { userMessage?: string; message?: string };
        setStatus(err?.userMessage || err?.message || "门套单价更新失败");
      }
    }
  }

  function addDoorGroup() {
    setDoorGroups((groups) => [...groups, createQuoteGroup(groups.length)]);
    setLastQuoteId(null);
  }

  function removeDoorGroup(groupIndex: number) {
    if (doorGroups.length <= 1) return;
    setDoorGroups((groups) => groups
      .filter((_, index) => index !== groupIndex)
      .map((group, index) => ({ ...group, groupName: `第${index + 1}樘门` })));
    setLastQuoteId(null);
  }

  // Load quote from history
  function handleLoadQuote(quote: QuoteResponse) {
    setCustomerName(quote.customerName);
    setProjectName(quote.projectName);
    setQuoteDate(quote.quoteDate);
    setNoticeText(quote.noticeText || DEFAULT_QUOTE_NOTICE_TEXT);
    const sourceGroups = quote.doorGroups?.length
      ? quote.doorGroups
      : [{
          groupName: "第1樘门",
          taskId: "",
          pricingMode: "outerArea" as QuotePricingMode,
          trimUnitPrice: 0,
          items: quote.items || [],
        }];
    setDoorGroups(sourceGroups.map((group, index) => ({
      groupName: group.groupName || `第${index + 1}樘门`,
      taskId: group.taskId || "",
      pricingMode: group.pricingMode || "outerArea",
      trimUnitPrice: group.trimUnitPrice || 0,
      items: normalizeQuoteRows((group.items || []).map((item) => ({
        accessoryId: item.accessoryId,
        category: item.category || "",
        productName: item.productName || "",
        width: item.width ?? null,
        height: item.height ?? null,
        quantity: item.quantity ?? null,
        openDirection: item.openDirection || "",
        unit: item.unit || "m2",
        unitPrice: item.unitPrice ?? 0,
      }))),
    })));
    setLastQuoteId(quote.id);
    setStatus(`已载入报价单 #${quote.id}`);
  }

  function handleClear() {
    setCustomerName("");
    setProjectName("");
    setQuoteDate(localDateYmd());
    setNoticeText(DEFAULT_QUOTE_NOTICE_TEXT);
    setDoorGroups([createQuoteGroup()]);
    setRememberQuote(false);
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
            type="button"
            aria-pressed={rememberQuote}
            onClick={() => setRememberQuote((enabled) => !enabled)}
            className={`px-3.5 py-1.5 text-[12px] font-medium rounded-lg border transition-colors ${
              rememberQuote
                ? "border-[#34C759] bg-[#34C759]/10 text-[#248A3D]"
                : "border-[#E5E5EA]/60 bg-white text-[#8E8E93] hover:bg-[#F2F2F7]"
            }`}
          >
            记忆报价：{rememberQuote ? "开" : "关"}
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
                  onChange={(e) => {
                    setCustomerName(e.target.value);
                    setLastQuoteId(null);
                  }}
                  placeholder="客户A"
                  className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
                />
              </label>
              <label className="block">
                <span className="text-[12px] font-medium text-[#8E8E93]">项目名称</span>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => {
                    setProjectName(e.target.value);
                    setLastQuoteId(null);
                  }}
                  placeholder="项目A"
                  className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
                />
              </label>
              <label className="block">
                <span className="text-[12px] font-medium text-[#8E8E93]">日期</span>
                <input
                  type="date"
                  value={quoteDate}
                  onChange={(e) => {
                    setQuoteDate(e.target.value);
                    setLastQuoteId(null);
                  }}
                  className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
                />
              </label>
            </div>
            <label className="block mb-4">
              <span className="text-[12px] font-medium text-[#8E8E93]">报价说明</span>
              <span className="ml-2 inline-flex gap-1">
                <button
                  type="button"
                  onClick={() => {
                    setNoticeText("本报价不含税工厂结算价，含木箱。");
                    setLastQuoteId(null);
                  }}
                  className="rounded-md bg-[#F2F2F7] px-2 py-1 text-[11px] text-[#1C1C1E]"
                >
                  含木箱
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setNoticeText("本报价不含税工厂结算价，不含木箱。");
                    setLastQuoteId(null);
                  }}
                  className="rounded-md bg-[#F2F2F7] px-2 py-1 text-[11px] text-[#1C1C1E]"
                >
                  不含木箱
                </button>
              </span>
              <input
                type="text"
                value={noticeText}
                onChange={(e) => {
                  setNoticeText(e.target.value);
                  setLastQuoteId(null);
                }}
                className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
              />
            </label>

            <div className="space-y-5">
              {doorGroups.map((group, groupIndex) => (
                <section key={groupIndex} className="border-t border-[#E5E5EA]/60 pt-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <input
                      value={group.groupName}
                      onChange={(event) => updateDoorGroup(groupIndex, { groupName: event.target.value })}
                      aria-label={`第 ${groupIndex + 1} 个门组名称`}
                      className="min-w-0 flex-1 bg-transparent text-[14px] font-semibold text-[#1C1C1E] outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => removeDoorGroup(groupIndex)}
                      disabled={doorGroups.length <= 1}
                      className="rounded-md px-2 py-1 text-[12px] text-[#FF3B30] hover:bg-[#FF3B30]/10 disabled:cursor-not-allowed disabled:opacity-25"
                    >
                      删除此门
                    </button>
                  </div>

                  <label className="mb-3 block">
                    <span className="text-[12px] font-medium text-[#8E8E93]">关联图纸项目</span>
                    <select
                      value={group.taskId}
                      onChange={(event) => handleApplyTaskQuote(
                        groupIndex,
                        event.target.value,
                        group.pricingMode,
                        group.trimUnitPrice,
                      )}
                      className="mt-1 w-full rounded-lg border border-[#E5E5EA]/60 bg-white px-3 py-2 text-[13px] focus:border-[#007AFF] focus:outline-none"
                    >
                      <option value="">选择图纸项目后自动报价</option>
                      {drawingTasks.map((task) => (
                        <option key={task.id} value={task.id}>
                          {task.customer || "未填客户"} / {task.project || "未填项目"} / {task.door_type || ""} / {task.size || ""}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="mb-3 bg-[#F8F8FA] p-3">
                    <div className="mb-2 text-[12px] font-medium text-[#8E8E93]">报价模式</div>
                    <div className="flex flex-wrap items-end gap-2">
                      <button
                        type="button"
                        onClick={() => handlePricingModeChange(groupIndex, "outerArea")}
                        className={`rounded-lg px-3 py-2 text-[12px] font-medium transition-colors ${
                          group.pricingMode === "outerArea"
                            ? "bg-[#007AFF] text-white"
                            : "border border-[#E5E5EA]/60 bg-white text-[#1C1C1E]"
                        }`}
                      >
                        外围面积 × 单价
                      </button>
                      <button
                        type="button"
                        onClick={() => handlePricingModeChange(groupIndex, "framePlusTrim")}
                        className={`rounded-lg px-3 py-2 text-[12px] font-medium transition-colors ${
                          group.pricingMode === "framePlusTrim"
                            ? "bg-[#007AFF] text-white"
                            : "border border-[#E5E5EA]/60 bg-white text-[#1C1C1E]"
                        }`}
                      >
                        门框面积 × 单价 + 门套面积 × 单价
                      </button>
                      {group.pricingMode === "framePlusTrim" && (
                        <label className="min-w-[150px]">
                          <span className="block text-[12px] font-medium text-[#8E8E93]">门套单价</span>
                          <input
                            type="number"
                            step="0.01"
                            value={group.trimUnitPrice || ""}
                            onChange={(event) => handleTrimUnitPriceChange(groupIndex, event.target.value)}
                            className="mt-1 w-full rounded-lg border border-[#E5E5EA]/60 px-3 py-2 text-[13px] focus:border-[#007AFF] focus:outline-none"
                          />
                        </label>
                      )}
                    </div>
                  </div>

                  <QuoteItemsTable
                    items={group.items}
                    onChange={(rows) => {
                      updateDoorGroup(groupIndex, { items: normalizeQuoteRows(rows) });
                      setLastQuoteId(null);
                    }}
                  />
                </section>
              ))}
            </div>

            <button
              type="button"
              onClick={addDoorGroup}
              className="mt-5 w-full rounded-lg border border-dashed border-[#007AFF] px-4 py-2 text-[13px] font-medium text-[#007AFF] hover:bg-[#007AFF]/5"
            >
              + 添加一樘门
            </button>
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
            doorGroups={doorGroups}
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
