"use client";

import { useState, useEffect, useCallback } from "react";
import { X } from "lucide-react";
import { getQuotes, deleteQuote, getQuote } from "@/lib/quoteApi";
import type { QuoteResponse, QuoteDoorGroupResponse } from "@/lib/quoteTypes";

interface Props {
  open: boolean;
  onClose: () => void;
  onLoad: (quote: QuoteResponse) => void;
}

function quoteDoorList(quote: QuoteResponse) {
  if (quote.doorSummary) {
    return [{
      name: quote.doorSummary,
      size: quote.doorWidth && quote.doorHeight ? `${quote.doorWidth} x ${quote.doorHeight}` : "尺寸未填",
    }];
  }
  const groups = quote.doorGroups?.length ? quote.doorGroups : [{ items: quote.items || [] }];
  return groups.map((group) => {
    const first = group.items.find((item) => item.productName?.trim());
    const groupName = (group as Partial<QuoteDoorGroupResponse>).groupName?.trim();
    return {
      name: first?.productName?.trim() || groupName || "未填写门型",
      size: first?.width && first?.height ? `${first.width} x ${first.height}` : "尺寸未填",
    };
  });
}

function quoteSearchText(quote: QuoteResponse) {
  return quoteDoorList(quote).map((door) => `${door.name} ${door.size}`).join(" ");
}

export default function QuoteHistoryModal({ open, onClose, onLoad }: Props) {
  const [quotes, setQuotes] = useState<QuoteResponse[]>([]);
  const [status, setStatus] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [keyword, setKeyword] = useState("");
  const [quoteDate, setQuoteDate] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await getQuotes();
      setQuotes(data.quotes || []);
      setSelectedIds((prev) => prev.filter((id) => (data.quotes || []).some((quote) => quote.id === id)));
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  async function handleLoad(id: number) {
    setStatus("");
    try {
      const quote = await getQuote(id);
      onClose();
      onLoad(quote);
    } catch (err: any) {
      setStatus(err?.userMessage || err?.message || "载入失败");
    }
  }

  async function handleDelete(id: number, customerName: string) {
    if (!confirm(`确定删除报价单 #${id}（${customerName}）？`)) return;
    try {
      await deleteQuote(id);
      setStatus(`报价单 #${id} 已删除`);
      await load();
    } catch (err: any) {
      setStatus(err?.userMessage || err?.message || "删除失败");
    }
  }

  async function handleBatchDelete() {
    if (selectedIds.length === 0) {
      setStatus("请先选择要删除的报价单");
      return;
    }
    if (!confirm(`确定删除选中的 ${selectedIds.length} 条报价单？删除后不可恢复。`)) return;
    try {
      await Promise.all(selectedIds.map((id) => deleteQuote(id)));
      setStatus(`已删除 ${selectedIds.length} 条报价单`);
      setSelectedIds([]);
      await load();
    } catch (err: any) {
      setStatus(err?.userMessage || err?.message || "批量删除失败");
    }
  }

  const filteredQuotes = quotes.filter((quote) => {
    const query = keyword.trim().toLowerCase();
    const matchesKeyword = !query || [quote.customerName, quote.projectName, String(quote.id), quoteSearchText(quote)]
      .join(" ").toLowerCase().includes(query);
    return matchesKeyword && (!quoteDate || quote.quoteDate === quoteDate);
  });
  const allSelected = filteredQuotes.length > 0 && filteredQuotes.every((quote) => selectedIds.includes(quote.id));

  if (!open) return null;

  return (
    <div className="ui-dialog-backdrop" onClick={onClose}>
      <div
        className="ui-dialog ui-dialog--wide"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="ui-dialog__header">
          <div>
            <h3 className="ui-dialog__title">最近报价</h3>
            <p className="ui-dialog__description">检索历史记录并载入继续编辑。</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleBatchDelete}
              disabled={selectedIds.length === 0}
              className="ui-button ui-button--danger"
            >
              批量删除
            </button>
            <button onClick={onClose} className="ui-dialog__close" aria-label="关闭"><X size={18} /></button>
          </div>
        </div>

        {/* Body */}
        <div className="ui-dialog__body">
          <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_170px_auto]">
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索报价单号、客户、项目"
              className="border border-[#D7D7DE] px-3 py-2 text-sm outline-none focus:border-[#007AFF]"
            />
            <input
              type="date"
              value={quoteDate}
              onChange={(event) => setQuoteDate(event.target.value)}
              className="border border-[#D7D7DE] px-3 py-2 text-sm outline-none focus:border-[#007AFF]"
            />
            <button type="button" onClick={() => { setKeyword(""); setQuoteDate(""); }} className="ui-button ui-button--quiet">清除筛选</button>
          </div>
          {status && (
            <p className={`mb-3 text-[13px] ${status.includes("失败") ? "text-[#C93531]" : "text-[#248A3D]"}`}>{status}</p>
          )}

          {filteredQuotes.length === 0 ? (
            <p className="text-[13px] text-[#8E8E93] text-center py-8">暂无报价记录</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-[#E5E5EA]/80">
              <label className="flex items-center gap-2 px-3 py-2 text-[12px] text-[#8E8E93] border-b border-[#F2F2F7]">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => setSelectedIds((previous) => e.target.checked
                    ? Array.from(new Set([...previous, ...filteredQuotes.map((quote) => quote.id)]))
                    : previous.filter((id) => !filteredQuotes.some((quote) => quote.id === id)))}
                />
                <span className="w-16">全选</span>
                <span className="w-20">报价单</span>
                <span className="min-w-36 flex-1">客户/项目</span>
                <span className="w-56">门型/尺寸</span>
                <span className="w-28">报价日期</span>
                <span className="w-16">操作</span>
              </label>
              {filteredQuotes.map((quote) => {
                const doors = quoteDoorList(quote);
                return (
                <div
                  key={quote.id}
                  className="flex items-center px-3 py-2.5 hover:bg-[#F2F2F7]/50 transition-colors group border-b border-[#F2F2F7] last:border-b-0"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(quote.id)}
                    onChange={(e) => {
                      setSelectedIds((prev) => e.target.checked ? [...prev, quote.id] : prev.filter((id) => id !== quote.id));
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="mr-2"
                  />
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center text-left"
                    onClick={() => handleLoad(quote.id)}
                  >
                    <span className="w-20 shrink-0 text-[13px] font-medium text-[#1C1C1E]">#{quote.id}</span>
                    <span className="min-w-0 flex-1 truncate text-[13px] text-[#1C1C1E]">{[quote.customerName, quote.projectName].filter(Boolean).join(" / ") || "未命名报价"}</span>
                    <span className="w-56 shrink-0 pr-3 text-xs text-[#3A3A3C]">
                      {doors.map((door, index) => (
                        <span key={index} className="flex items-baseline gap-1">
                          <span className="block truncate max-w-[190px]">{door.name}</span>
                          <span className="block text-[#8E8E93] whitespace-nowrap">{door.size}</span>
                        </span>
                      ))}
                    </span>
                    <span className="w-28 shrink-0 text-xs text-[#777780]">{quote.quoteDate || "-"}</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(quote.id, quote.customerName);
                    }}
                    className="whitespace-nowrap px-2 py-1 text-xs text-[#C93531] opacity-70 transition-all hover:opacity-100 group-hover:opacity-100"
                  >
                    删除
                  </button>
                </div>
                );
              })}
            </div>
          )}
        </div>
        <div className="ui-dialog__footer justify-between">
          <span className="text-xs text-[#777780]">共 {filteredQuotes.length} 条记录</span>
          <button type="button" onClick={onClose} className="ui-button ui-button--secondary">关闭</button>
        </div>
      </div>
    </div>
  );
}
