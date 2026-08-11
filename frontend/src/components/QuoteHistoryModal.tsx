"use client";

import { useState, useEffect, useCallback } from "react";
import { getQuotes, deleteQuote, getQuote } from "@/lib/quoteApi";
import type { QuoteResponse } from "@/lib/quoteTypes";

interface Props {
  open: boolean;
  onClose: () => void;
  onLoad: (quote: QuoteResponse) => void;
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
    const matchesKeyword = !query || [quote.customerName, quote.projectName, String(quote.id)]
      .join(" ").toLowerCase().includes(query);
    return matchesKeyword && (!quoteDate || quote.quoteDate === quoteDate);
  });
  const allSelected = filteredQuotes.length > 0 && filteredQuotes.every((quote) => selectedIds.includes(quote.id));

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[75vh] flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E5E5EA]/60">
          <h3 className="text-[16px] font-semibold text-[#1C1C1E]">最近报价</h3>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleBatchDelete}
              disabled={selectedIds.length === 0}
              className="px-3 py-1.5 rounded-lg text-[12px] font-medium bg-[#FF3B30]/10 text-[#FF3B30] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              批量删除
            </button>
            <button onClick={onClose} className="text-[#8E8E93] hover:text-[#1C1C1E] text-[20px] leading-none transition-colors">&times;</button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_170px_auto]">
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="搜索报价单号、客户、项目"
              className="rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px] outline-none focus:border-[#007AFF]"
            />
            <input
              type="date"
              value={quoteDate}
              onChange={(event) => setQuoteDate(event.target.value)}
              className="rounded-lg border border-[#E5E5EA] px-3 py-2 text-[13px] outline-none focus:border-[#007AFF]"
            />
            <button type="button" onClick={() => { setKeyword(""); setQuoteDate(""); }} className="rounded-lg px-3 py-2 text-[13px] text-[#007AFF] hover:bg-[#F2F2F7]">清除筛选</button>
          </div>
          {status && (
            <p className={`text-[12px] mb-3 ${status.includes("失败") ? "text-[#FF3B30]" : "text-[#34C759]"}`}>{status}</p>
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
                <span className="min-w-40 flex-1">客户/项目</span>
                <span className="w-28">报价日期</span>
                <span className="w-16">操作</span>
              </label>
              {filteredQuotes.map((quote) => (
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
                    <span className="w-28 shrink-0 text-[11px] text-[#8E8E93]">{quote.quoteDate || "-"}</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(quote.id, quote.customerName);
                    }}
                    className="text-[11px] text-[#FF3B30]/60 hover:text-[#FF3B30] opacity-0 group-hover:opacity-100 transition-all px-2 py-1 whitespace-nowrap"
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
