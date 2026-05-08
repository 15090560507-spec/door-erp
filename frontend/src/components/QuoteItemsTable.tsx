"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { QuoteItem } from "@/lib/quoteTypes";
import { normalizeOpenDirection, UNIT_OPTIONS } from "@/lib/quoteTypes";
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
        productName: acc.name,
        unit: acc.unit || "m2",
        unitPrice: acc.unitPrice ?? 0,
      };
    });
    onChange(next);
    setSuggestions(null);
  }

  return (
    <div ref={containerRef} className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-[#E5E5EA]/60">
            <th className="text-left py-2 px-2 font-medium text-[#8E8E93] w-[200px]">品名型号</th>
            <th className="text-left py-2 px-2 font-medium text-[#8E8E93] w-[70px]">宽</th>
            <th className="text-left py-2 px-2 font-medium text-[#8E8E93] w-[70px]">高</th>
            <th className="text-left py-2 px-2 font-medium text-[#8E8E93] w-[80px]">开启方向</th>
            <th className="text-left py-2 px-2 font-medium text-[#8E8E93] w-[70px]">单位</th>
            <th className="text-left py-2 px-2 font-medium text-[#8E8E93] w-[90px]">单价</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={index} className="border-b border-[#E5E5EA]/30 hover:bg-[#F2F2F7]/50 transition-colors">
              {/* 品名型号 with search suggestions */}
              <td className="py-1.5 px-2 relative">
                <input
                  type="text"
                  value={item.productName}
                  onChange={(e) => handleProductSearch(index, e.target.value)}
                  placeholder="输入或搜索配件"
                  className="w-full px-2 py-1.5 text-[13px] bg-transparent border border-transparent rounded-md focus:border-[#007AFF] focus:bg-white focus:outline-none transition-colors placeholder:text-[#C7C7CC]"
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
              <td className="py-1.5 px-2">
                <input
                  type="number"
                  step="1"
                  value={item.width ?? ""}
                  onChange={(e) => updateItem(index, "width", e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-2 py-1.5 text-[13px] bg-transparent border border-transparent rounded-md focus:border-[#007AFF] focus:bg-white focus:outline-none transition-colors"
                />
              </td>
              {/* 高 */}
              <td className="py-1.5 px-2">
                <input
                  type="number"
                  step="1"
                  value={item.height ?? ""}
                  onChange={(e) => updateItem(index, "height", e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-2 py-1.5 text-[13px] bg-transparent border border-transparent rounded-md focus:border-[#007AFF] focus:bg-white focus:outline-none transition-colors"
                />
              </td>
              {/* 开启方向 */}
              <td className="py-1.5 px-2">
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
                  className="w-full px-2 py-1.5 text-[13px] bg-transparent border border-transparent rounded-md focus:border-[#007AFF] focus:bg-white focus:outline-none transition-colors placeholder:text-[#C7C7CC]"
                />
              </td>
              {/* 单位 */}
              <td className="py-1.5 px-2">
                <input
                  type="text"
                  value={item.unit}
                  onChange={(e) => updateItem(index, "unit", e.target.value)}
                  list="unitOptions"
                  className="w-full px-2 py-1.5 text-[13px] bg-transparent border border-transparent rounded-md focus:border-[#007AFF] focus:bg-white focus:outline-none transition-colors"
                />
              </td>
              {/* 单价 */}
              <td className="py-1.5 px-2">
                <input
                  type="number"
                  step="0.01"
                  value={item.unitPrice || ""}
                  onChange={(e) => updateItem(index, "unitPrice", e.target.value ? Number(e.target.value) : 0)}
                  className="w-full px-2 py-1.5 text-[13px] bg-transparent border border-transparent rounded-md focus:border-[#007AFF] focus:bg-white focus:outline-none transition-colors"
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <datalist id="unitOptions">
        {UNIT_OPTIONS.map((u) => (
          <option key={u} value={u} />
        ))}
      </datalist>
    </div>
  );
}
