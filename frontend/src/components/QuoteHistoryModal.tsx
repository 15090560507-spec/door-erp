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

  const load = useCallback(async () => {
    try {
      const data = await getQuotes();
      setQuotes(data.quotes || []);
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
          <button onClick={onClose} className="text-[#8E8E93] hover:text-[#1C1C1E] text-[20px] leading-none transition-colors">&times;</button>
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
              {quotes.map((quote) => (
                <div
                  key={quote.id}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-[#F2F2F7]/50 transition-colors group"
                >
                  <button
                    type="button"
                    className="flex-1 text-left min-w-0"
                    onClick={() => handleLoad(quote.id)}
                  >
                    <span className="text-[13px] font-medium text-[#1C1C1E]">
                      #{quote.id} {quote.customerName}
                    </span>
                    <span className="ml-2 text-[11px] text-[#8E8E93]">
                      {quote.projectName} / {quote.quoteDate}
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
