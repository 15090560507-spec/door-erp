"use client";

import { useState, useEffect, useRef, useId } from "react";
import type { QuoteItem } from "@/lib/quoteTypes";
import {
  createEmptyQuoteItem,
  normalizeOpenDirection,
  quoteItemAmountText,
  quoteItemQuantityText,
  UNIT_OPTIONS,
} from "@/lib/quoteTypes";
import { getAccessories } from "@/lib/quoteApi";
import type { Accessory } from "@/lib/quoteTypes";

interface Props {
  items: QuoteItem[];
  onChange: (items: QuoteItem[]) => void;
}

export default function QuoteItemsTable({ items, onChange }: Props) {
  const [suggestions, setSuggestions] = useState<{ index: number; matches: Accessory[] } | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const unitOptionsId = useId();
  const totalAmount = items.reduce((sum, item) => {
    const amount = Number(quoteItemAmountText(item));
    return sum + (Number.isFinite(amount) ? amount : 0);
  }, 0);

  // Close suggestions on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSuggestions(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function updateItem(index: number, field: keyof QuoteItem, value: string | number | null) {
    const next = items.map((item, i) => {
      if (i !== index) return item;
      if (field === "productName" && !String(value || "").trim()) {
        return { ...createEmptyQuoteItem(), rowId: item.rowId };
      }
      const updated = { ...item, [field]: value };
      // Clear accessoryId when productName is manually changed
      if (field === "productName") updated.accessoryId = null;
      return updated;
    });
    onChange(next);
  }

  async function handleProductSearch(index: number, query: string) {
    updateItem(index, "productName", query);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (!query.trim()) {
      setSuggestions(null);
      return;
    }
    searchTimer.current = setTimeout(async () => {
      try {
        const matches = await getAccessories(query);
        if (matches.length) {
          setSuggestions({ index, matches });
        } else {
          setSuggestions(null);
        }
      } catch {
        setSuggestions(null);
      }
    }, 200);
  }

  function selectAccessory(rowIndex: number, acc: Accessory) {
    const next = items.map((item, i) => {
      if (i !== rowIndex) return item;
      return {
        ...item,
        accessoryId: acc.id,
        category: acc.category || "",
        productName: acc.name,
        unit: acc.unit || "m2",
        unitPrice: acc.unitPrice ?? 0,
      };
    });
    onChange(next);
    setSuggestions(null);
  }

  function addRow() {
    onChange([...items, createEmptyQuoteItem()]);
  }

  function removeRow(index: number) {
    if (items.length <= 1) return;
    onChange(items.filter((_, rowIndex) => rowIndex !== index));
    setSuggestions(null);
  }

  return (
    <div ref={containerRef} className="w-full min-w-0 pb-1">
      <table className="w-full table-fixed text-[12px] xl:text-[13px]">
        <colgroup>
          <col className="w-[30%]" />
          <col className="w-[7%]" />
          <col className="w-[7%]" />
          <col className="w-[11%]" />
          <col className="w-[7%]" />
          <col className="w-[9%]" />
          <col className="w-[9%]" />
          <col className="w-[12%]" />
          <col className="w-[8%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-[#E5E5EA]/60">
            <th className="px-2 py-2 text-left font-medium text-[#8E8E93]">品名型号</th>
            <th className="px-1 py-2 text-left font-medium text-[#8E8E93]">宽</th>
            <th className="px-1 py-2 text-left font-medium text-[#8E8E93]">高</th>
            <th className="px-1 py-2 text-left font-medium text-[#8E8E93]">开启方向</th>
            <th className="px-1 py-2 text-left font-medium text-[#8E8E93]">单位</th>
            <th className="px-1 py-2 text-left font-medium text-[#8E8E93]">数量</th>
            <th className="px-1 py-2 text-left font-medium text-[#8E8E93]">单价</th>
            <th className="px-1 py-2 text-left font-medium text-[#8E8E93]">总金额</th>
            <th className="px-1 py-2 text-center font-medium text-[#8E8E93]">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={item.rowId || `quote-row-${index}`} className="border-b border-[#E5E5EA]/30 hover:bg-[#F2F2F7]/50 transition-colors">
              {/* 品名型号 with search suggestions */}
              <td className="relative px-2 py-1.5 align-top">
                <textarea
                  rows={2}
                  value={item.productName}
                  onChange={(e) => handleProductSearch(index, e.target.value)}
                  placeholder="输入或搜索配件"
                  className="min-h-12 w-full resize-y rounded-md border border-transparent bg-transparent px-1.5 py-1.5 text-[12px] leading-4 transition-colors placeholder:text-[#C7C7CC] focus:border-[#007AFF] focus:bg-white focus:outline-none xl:text-[13px]"
                />
                {suggestions?.index === index && (
                  <div className="absolute left-2 right-2 top-full z-20 bg-white border border-[#E5E5EA]/60 rounded-lg shadow-lg max-h-[200px] overflow-y-auto">
                    {suggestions.matches.slice(0, 6).map((acc) => (
                      <button
                        key={acc.id}
                        type="button"
                        onClick={() => selectAccessory(index, acc)}
                        className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F2F2F7] transition-colors border-b border-[#E5E5EA]/30 last:border-b-0"
                      >
                        <span className="font-medium text-[#1C1C1E]">{acc.name}</span>
                        <span className="ml-2 text-[#8E8E93] text-[11px]">
                          {acc.category || "未分类"} / {acc.unit || "m2"} / ¥{acc.unitPrice ?? 0}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </td>
              {/* 宽 */}
              <td className="px-1 py-1.5 align-top">
                <input
                  type="number"
                  step="1"
                  value={item.width ?? ""}
                  onChange={(e) => updateItem(index, "width", e.target.value ? Number(e.target.value) : null)}
                  className="w-full min-w-0 rounded-md border border-transparent bg-transparent px-1 py-1.5 text-[12px] transition-colors focus:border-[#007AFF] focus:bg-white focus:outline-none xl:text-[13px]"
                />
              </td>
              {/* 高 */}
              <td className="px-1 py-1.5 align-top">
                <input
                  type="number"
                  step="1"
                  value={item.height ?? ""}
                  onChange={(e) => updateItem(index, "height", e.target.value ? Number(e.target.value) : null)}
                  className="w-full min-w-0 rounded-md border border-transparent bg-transparent px-1 py-1.5 text-[12px] transition-colors focus:border-[#007AFF] focus:bg-white focus:outline-none xl:text-[13px]"
                />
              </td>
              {/* 开启方向 */}
              <td className="px-1 py-1.5 align-top">
                <input
                  type="text"
                  value={item.openDirection}
                  onChange={(e) => updateItem(index, "openDirection", e.target.value)}
                  onBlur={(e) => {
                    const normalized = normalizeOpenDirection(e.target.value);
                    if (normalized !== e.target.value) {
                      updateItem(index, "openDirection", normalized);
                    }
                  }}
                  placeholder="如: 内右开"
                  className="w-full min-w-0 rounded-md border border-transparent bg-transparent px-1 py-1.5 text-[12px] transition-colors placeholder:text-[#C7C7CC] focus:border-[#007AFF] focus:bg-white focus:outline-none xl:text-[13px]"
                />
              </td>
              {/* 单位 */}
              <td className="px-1 py-1.5 align-top">
                <input
                  type="text"
                  value={item.unit}
                  onChange={(e) => updateItem(index, "unit", e.target.value)}
                  list={unitOptionsId}
                  className="w-full min-w-0 rounded-md border border-transparent bg-transparent px-1 py-1.5 text-[12px] transition-colors focus:border-[#007AFF] focus:bg-white focus:outline-none xl:text-[13px]"
                />
              </td>
              {/* 数量 */}
              <td className="px-1 py-1.5 align-top">
                <input
                  type="number"
                  step="0.0001"
                  value={item.quantity ?? quoteItemQuantityText(item)}
                  onChange={(e) => updateItem(index, "quantity", e.target.value ? Number(e.target.value) : null)}
                  placeholder="自动"
                  title={item.quantity === null || item.quantity === undefined ? "自动计算数量" : "手动数量"}
                  className="w-full min-w-0 rounded-md border border-transparent bg-transparent px-1 py-1.5 text-[12px] transition-colors placeholder:text-[#C7C7CC] focus:border-[#007AFF] focus:bg-white focus:outline-none xl:text-[13px]"
                />
              </td>
              {/* 单价 */}
              <td className="px-1 py-1.5 align-top">
                <input
                  type="number"
                  step="0.01"
                  value={item.unitPrice || ""}
                  onChange={(e) => updateItem(index, "unitPrice", e.target.value ? Number(e.target.value) : 0)}
                  className="w-full min-w-0 rounded-md border border-transparent bg-transparent px-1 py-1.5 text-[12px] transition-colors focus:border-[#007AFF] focus:bg-white focus:outline-none xl:text-[13px]"
                />
              </td>
              <td className="break-all px-1 py-3 text-right align-top font-medium tabular-nums text-[#1C1C1E]">
                {quoteItemAmountText(item)}
              </td>
              <td className="px-1 py-2 text-center align-top">
                <button
                  type="button"
                  onClick={() => removeRow(index)}
                  disabled={items.length <= 1}
                  aria-label={`删除第 ${index + 1} 行`}
                  className="rounded-md px-2 py-1 text-[12px] text-[#FF3B30] hover:bg-[#FF3B30]/10 disabled:cursor-not-allowed disabled:opacity-25"
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-[#1C1C1E] bg-[#F2F2F7]/70">
            <td colSpan={7} className="px-3 py-2 text-right text-[13px] font-semibold text-[#1C1C1E]">总价</td>
            <td className="px-4 py-2 text-right text-[14px] font-semibold tabular-nums text-[#1C1C1E]">{totalAmount}</td>
            <td />
          </tr>
        </tfoot>
      </table>
      <button
        type="button"
        onClick={addRow}
        className="mt-2 rounded-lg border border-dashed border-[#C7C7CC] px-3 py-1.5 text-[12px] font-medium text-[#007AFF] hover:border-[#007AFF] hover:bg-[#007AFF]/5"
      >
        + 添加明细
      </button>
      <datalist id={unitOptionsId}>
        {UNIT_OPTIONS.map((u) => (
          <option key={u} value={u} />
        ))}
      </datalist>
    </div>
  );
}
