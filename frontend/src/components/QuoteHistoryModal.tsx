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

  const allSelected = quotes.length > 0 && selectedIds.length === quotes.length;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[75vh] flex flex-col mx-4"
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
          {status && (
            <p className={`text-[12px] mb-3 ${status.includes("失败") ? "text-[#FF3B30]" : "text-[#34C759]"}`}>{status}</p>
          )}

          {quotes.length === 0 ? (
            <p className="text-[13px] text-[#8E8E93] text-center py-8">暂无报价记录</p>
          ) : (
            <div className="space-y-1">
              <label className="flex items-center gap-2 px-3 py-2 text-[12px] text-[#8E8E93] border-b border-[#F2F2F7]">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => setSelectedIds(e.target.checked ? quotes.map((quote) => quote.id) : [])}
                />
                全选当前列表
              </label>
              {quotes.map((quote) => (
                <div
                  key={quote.id}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-[#F2F2F7]/50 transition-colors group"
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
                    className="flex-1 text-left min-w-0"
                    onClick={() => handleLoad(quote.id)}
                  >
                    <span className="text-[13px] font-medium text-[#1C1C1E]">
                      #{quote.id} {quote.customerName}
                    </span>
                    <span className="ml-2 text-[11px] text-[#8E8E93]">
                      {[quote.projectName, quote.quoteDate].filter(Boolean).join(" / ")}
                    </span>
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
