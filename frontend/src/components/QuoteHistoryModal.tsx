"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, RefreshCw, X } from "lucide-react";
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

const PAGE_SIZE = 50;

export default function QuoteHistoryModal({ open, onClose, onLoad }: Props) {
  const [quotes, setQuotes] = useState<QuoteResponse[]>([]);
  const [status, setStatus] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [keyword, setKeyword] = useState("");
  const [quoteDate, setQuoteDate] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [statusError, setStatusError] = useState(false);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setLoadError("");
      setSelectedIds([]);
      try {
        const data = await getQuotes({ limit: PAGE_SIZE, offset, q: keyword.trim(), quoteDate }, controller.signal);
        if (controller.signal.aborted) return;
        if (offset > 0 && offset >= data.total) {
          setOffset(Math.max(0, Math.floor((data.total - 1) / PAGE_SIZE) * PAGE_SIZE));
          return;
        }
        setQuotes(data.quotes);
        setTotal(data.total);
        setLoading(false);
      } catch (error: unknown) {
        if (controller.signal.aborted) return;
        setLoadError(errorMessage(error, "报价历史加载失败"));
        setLoading(false);
      }
    }, keyword ? 250 : 0);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [open, offset, keyword, quoteDate, revision]);

  function refresh() {
    setLoading(true);
    setSelectedIds([]);
    setRevision((value) => value + 1);
  }

  function changePage(nextOffset: number) {
    setLoading(true);
    setSelectedIds([]);
    setOffset(nextOffset);
  }

  function changeFilter(nextKeyword: string, nextDate: string) {
    changePage(0);
    setKeyword(nextKeyword);
    setQuoteDate(nextDate);
    setRevision((value) => value + 1);
  }

  async function handleLoad(id: number) {
    setStatus("");
    setBusy(true);
    try {
      const quote = await getQuote(id);
      onClose();
      onLoad(quote);
    } catch (error: unknown) {
      setStatusError(true);
      setStatus(errorMessage(error, "载入失败"));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: number, customerName: string) {
    if (!confirm(`确定删除报价单 #${id}（${customerName}）？`)) return;
    setBusy(true);
    try {
      await deleteQuote(id);
      setStatusError(false);
      setStatus(`报价单 #${id} 已删除`);
    } catch (error: unknown) {
      setStatusError(true);
      setStatus(errorMessage(error, "删除失败"));
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function handleBatchDelete() {
    if (selectedIds.length === 0) {
      setStatus("请先选择要删除的报价单");
      return;
    }
    if (!confirm(`确定删除选中的 ${selectedIds.length} 条报价单？删除后不可恢复。`)) return;
    setBusy(true);
    try {
      const results = await Promise.allSettled(selectedIds.map((id) => deleteQuote(id)));
      const failed = results.filter((result) => result.status === "rejected");
      setStatusError(failed.length > 0);
      setStatus(failed.length
        ? `已删除 ${results.length - failed.length} 条，${failed.length} 条删除失败，请重试`
        : `已删除 ${results.length} 条报价单`);
    } catch (error: unknown) {
      setStatusError(true);
      setStatus(errorMessage(error, "批量删除失败"));
    } finally {
      setBusy(false);
      refresh();
    }
  }

  const allSelected = quotes.length > 0 && quotes.every((quote) => selectedIds.includes(quote.id));

  if (!open) return null;

  return (
    <div className="ui-dialog-backdrop" onClick={onClose}>
      <div
        className="ui-dialog ui-dialog--wide"
        role="dialog"
        aria-modal="true"
        aria-label="报价历史"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="ui-dialog__header">
          <div>
            <h3 className="ui-dialog__title">报价历史</h3>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleBatchDelete}
              disabled={selectedIds.length === 0 || busy || loading || !!loadError}
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
              onChange={(event) => changeFilter(event.target.value, quoteDate)}
              placeholder="搜索报价单号、客户、项目、门型或尺寸"
              aria-label="搜索报价历史"
              disabled={busy}
              className="border border-[#D7D7DE] px-3 py-2 text-sm outline-none focus:border-[#007AFF]"
            />
            <input
              type="date"
              value={quoteDate}
              onChange={(event) => changeFilter(keyword, event.target.value)}
              aria-label="报价日期"
              disabled={busy}
              className="border border-[#D7D7DE] px-3 py-2 text-sm outline-none focus:border-[#007AFF]"
            />
            <button type="button" disabled={busy} onClick={() => changeFilter("", "")} className="ui-button ui-button--quiet">清除筛选</button>
          </div>
          {status && (
            <p role="status" className={`mb-3 text-[13px] ${statusError ? "text-[#C93531]" : "text-[#248A3D]"}`}>{status}</p>
          )}

          {loading ? (
            <p role="status" className="py-8 text-center text-sm text-[#777780]">加载中…</p>
          ) : loadError ? (
            <div role="alert" className="flex flex-wrap items-center justify-center gap-3 py-8 text-sm text-[#C93531]">
              <span>{loadError}</span>
              <button type="button" onClick={refresh} className="ui-button ui-button--secondary"><RefreshCw size={16} />重试</button>
            </div>
          ) : quotes.length === 0 ? (
            <p className="text-[13px] text-[#8E8E93] text-center py-8">暂无报价记录</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-[#E5E5EA]/80">
              <label className="flex min-w-[800px] items-center px-3 py-2 text-[12px] text-[#8E8E93] border-b border-[#F2F2F7]">
                <input
                  type="checkbox"
                  checked={allSelected}
                  disabled={busy}
                  aria-label="全选本页"
                  className="mr-2"
                  onChange={(e) => setSelectedIds(e.target.checked ? quotes.map((quote) => quote.id) : [])}
                />
                <span className="w-20 shrink-0">全选本页</span>
                <span className="min-w-36 flex-1">客户/项目</span>
                <span className="w-56">门型/尺寸</span>
                <span className="w-28">报价日期</span>
                <span className="w-16">操作</span>
              </label>
              {quotes.map((quote) => {
                const doors = quoteDoorList(quote);
                return (
                <div
                  key={quote.id}
                  className="flex min-w-[800px] items-center px-3 py-2.5 hover:bg-[#F2F2F7]/50 transition-colors group border-b border-[#F2F2F7] last:border-b-0"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(quote.id)}
                    disabled={busy}
                    aria-label={`选择报价单 #${quote.id}`}
                    onChange={(e) => {
                      setSelectedIds((prev) => e.target.checked ? [...prev, quote.id] : prev.filter((id) => id !== quote.id));
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="mr-2"
                  />
                  <button
                    type="button"
                    disabled={busy}
                    className="flex min-w-0 flex-1 items-center text-left"
                    onClick={() => handleLoad(quote.id)}
                  >
                    <span className="w-20 shrink-0 text-[13px] font-medium text-[#1C1C1E]">#{quote.id}</span>
                    <span className="min-w-0 flex-1 truncate text-[13px] text-[#1C1C1E]">{[quote.customerName, quote.projectName].filter(Boolean).join(" / ") || "未命名报价"}</span>
                    <span className="w-56 shrink-0 pr-3 text-xs text-[#3A3A3C]">
                      {doors.map((door, index) => (
                        <span key={index} className="block">
                          <span className="block truncate" title={door.name}>{door.name}</span>
                          <span className="block text-[#8E8E93] whitespace-nowrap">{door.size}</span>
                        </span>
                      ))}
                    </span>
                    <span className="w-28 shrink-0 text-xs text-[#777780]">{quote.quoteDate || "-"}</span>
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(quote.id, quote.customerName);
                    }}
                    className="w-16 shrink-0 whitespace-nowrap px-2 py-1 text-xs text-[#C93531] opacity-70 transition-all hover:opacity-100 group-hover:opacity-100"
                  >
                    删除
                  </button>
                </div>
                );
              })}
            </div>
          )}
        </div>
        <div className="ui-dialog__footer" style={{ flexWrap: "wrap", justifyContent: "space-between", gap: 8 }}>
          <span className="text-xs text-[#777780]">{loading || loadError ? "" : `共 ${total} 条记录${total ? ` · ${offset + 1}–${offset + quotes.length}` : ""}`}</span>
          <div className="flex items-center gap-2">
            <button type="button" title="上一页" aria-label="上一页" onClick={() => changePage(offset - PAGE_SIZE)} disabled={loading || busy || !!loadError || offset === 0} className="ui-button ui-button--secondary"><ChevronLeft size={16} /></button>
            <span className="text-xs text-[#777780]">{Math.floor(offset / PAGE_SIZE) + 1} / {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span>
            <button type="button" title="下一页" aria-label="下一页" onClick={() => changePage(offset + PAGE_SIZE)} disabled={loading || busy || !!loadError || offset + PAGE_SIZE >= total} className="ui-button ui-button--secondary"><ChevronRight size={16} /></button>
          </div>
          <button type="button" onClick={onClose} className="ui-button ui-button--secondary">关闭</button>
        </div>
      </div>
    </div>
  );
}

function errorMessage(error: unknown, fallback: string) {
  return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback;
}
