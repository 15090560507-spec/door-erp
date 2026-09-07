"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import {
  createAccessory,
  deleteAccessory,
  exportAccessories,
  getAccessories,
  importAccessories,
  importAccessoriesXlsx,
} from "@/lib/quoteApi";
import type { Accessory } from "@/lib/quoteTypes";
import { localDateYmd } from "@/lib/dateTime";

interface Props {
  open: boolean;
  onClose: () => void;
}

const BASE_CATEGORIES = ["制作材料", "款式组合", "锁体", "合页", "配件", "包装"];

function inferUnit(category: string) {
  return ["制作材料", "款式组合", "锁体", "包装"].includes(category) ? "m2" : "套";
}

function inferPriceMode(category: string) {
  if (category === "款式组合") return "area_base";
  if (category === "包装") return "outer_area_add";
  if (["制作材料", "锁体"].includes(category)) return "area_add";
  return "piece";
}

function inferPriceType(category: string) {
  if (category === "制作材料") return "material";
  if (category === "款式组合") return "style_combo";
  if (category === "锁体") return "lock_body";
  if (category === "包装") return "packing";
  return "hardware";
}

function errorMessage(error: unknown, fallback: string) {
  const err = error as { userMessage?: string; message?: string };
  return err?.userMessage || err?.message || fallback;
}

export default function AccessoryModal({ open, onClose }: Props) {
  const [accessories, setAccessories] = useState<Accessory[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("配件");
  const [name, setName] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (q?: string) => {
    const data = await getAccessories(q);
    setAccessories(data);
  }, []);

  useEffect(() => {
    if (!open) return;
    load(search).catch(() => setStatus("配件库加载失败"));
  }, [open, load]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      load(search).catch(() => setStatus("配件库搜索失败"));
    }, 250);
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, [search, load, open]);

  const categories = useMemo(() => {
    const values = new Set(BASE_CATEGORIES);
    accessories.forEach((item) => {
      if (item.category) values.add(item.category);
    });
    return Array.from(values);
  }, [accessories]);

  const groupedAccessories = useMemo(() => {
    const groups = new Map<string, Accessory[]>();
    accessories.forEach((item) => {
      const key = item.category || "未分类";
      const group = groups.get(key) || [];
      group.push(item);
      groups.set(key, group);
    });
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b, "zh-CN"));
  }, [accessories]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const finalName = name.trim();
    const finalCategory = category.trim() || "配件";
    if (!finalName) {
      setStatus("请填写名称");
      return;
    }
    setSubmitting(true);
    setStatus("");
    try {
      await createAccessory({
        name: finalName,
        category: finalCategory,
        keywords: finalName,
        unit: inferUnit(finalCategory),
        unitPrice: unitPrice ? Number(unitPrice) : 0,
        remark: "",
        priceType: inferPriceType(finalCategory),
        priceMode: inferPriceMode(finalCategory),
      });
      setName("");
      setUnitPrice("");
      setStatus("已添加");
      await load(search);
    } catch (error: unknown) {
      setStatus(errorMessage(error, "添加失败"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteAccessory(id);
      setStatus("已删除");
      await load(search);
    } catch (error: unknown) {
      setStatus(errorMessage(error, "删除失败"));
    }
  }

  async function handleExport() {
    try {
      const data = await exportAccessories();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `配件价格库_${localDateYmd()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus(`已导出 ${data.length} 条`);
    } catch {
      setStatus("导出失败");
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      if (/\.(xlsx|xlsm)$/i.test(file.name)) {
        const result = await importAccessoriesXlsx(file);
        setStatus(`成功导入/更新 ${result.imported} 条`);
      } else {
        const text = await file.text();
        const json = JSON.parse(text);
        const items = Array.isArray(json) ? json : json.accessories;
        if (!Array.isArray(items) || !items.length) {
          setStatus("文件中没有有效数据");
          return;
        }
        const result = await importAccessories(items);
        setStatus(`成功导入 ${result.imported} 条`);
      }
      setSearch("");
      await load();
    } catch (error: unknown) {
      setStatus(errorMessage(error, "导入失败，请检查文件格式"));
    } finally {
      e.target.value = "";
    }
  }

  if (!open) return null;

  return (
    <div className="ui-dialog-backdrop" onClick={onClose}>
      <div
        className="ui-dialog ui-dialog--wide"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="ui-dialog__header">
          <div>
            <h3 className="ui-dialog__title">配件价格库</h3>
            <p className="ui-dialog__description">按价格表方式维护分类、名称和单价。</p>
          </div>
          <button onClick={onClose} className="ui-dialog__close" aria-label="关闭"><X size={18} /></button>
        </div>

        <div className="ui-dialog__body space-y-4">
          <form onSubmit={handleAdd} className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[150px_1fr_130px_auto]">
            <label className="block">
              <span className="text-[13px] font-medium text-[#62626B]">分类</span>
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                list="accessoryCategoryOptions"
                className="mt-1 w-full border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="text-[13px] font-medium text-[#62626B]">名称</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
                required
              />
            </label>
            <label className="block">
              <span className="text-[13px] font-medium text-[#62626B]">单价</span>
              <input
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                type="number"
                step="0.01"
                className="mt-1 w-full border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
              />
            </label>
            <button
              type="submit"
              disabled={submitting}
              className="ui-button ui-button--primary"
            >
              {submitting ? "添加中..." : "添加"}
            </button>
            <datalist id="accessoryCategoryOptions">
              {categories.map((item) => <option key={item} value={item} />)}
            </datalist>
          </form>

          <div className="flex gap-3 items-center">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索分类或名称"
              className="min-w-0 flex-1 border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
            />
            <button onClick={handleExport} type="button" className="ui-button ui-button--secondary whitespace-nowrap">导出</button>
            <label className="ui-button ui-button--secondary cursor-pointer whitespace-nowrap">
              导入 Excel/JSON
              <input type="file" accept=".json,.xlsx,.xlsm" onChange={handleImport} className="hidden" />
            </label>
          </div>

          {status && <div className="text-[13px] text-[#4F62A7]">{status}</div>}

          <div className="space-y-4">
            {groupedAccessories.length === 0 ? (
              <p className="text-[13px] text-[#8E8E93] text-center py-6">暂无数据</p>
            ) : (
              groupedAccessories.map(([groupName, groupItems]) => (
                <section key={groupName} className="overflow-hidden border border-[#E2E2E8]">
                  <div className="px-3 py-2 bg-[#F2F2F7] text-[13px] font-semibold text-[#1C1C1E] flex items-center justify-between">
                    <span>{groupName}</span>
                    <span className="text-xs font-normal text-[#777780]">{groupItems.length} 条</span>
                  </div>
                  <table className="w-full text-[13px]">
                    <thead className="text-[#8E8E93] border-b border-[#E5E5EA]/60">
                      <tr>
                        <th className="text-left font-medium px-3 py-2">名称</th>
                        <th className="text-right font-medium px-3 py-2 w-32">单价</th>
                        <th className="px-3 py-2 w-20"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {groupItems.map((item) => (
                        <tr key={item.id} className="border-b border-[#F2F2F7] last:border-b-0 hover:bg-[#FAFAFC]">
                          <td className="px-3 py-2 text-[#1C1C1E]">{item.name}</td>
                          <td className="px-3 py-2 text-right text-[#1C1C1E]">{item.unitPrice ?? 0}</td>
                          <td className="px-3 py-2 text-right">
                            <button
                              onClick={() => handleDelete(item.id)}
                              className="text-[12px] text-[#FF3B30] hover:underline"
                            >
                              删除
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              ))
            )}
          </div>
        </div>
        <div className="ui-dialog__footer">
          <button type="button" onClick={onClose} className="ui-button ui-button--secondary">关闭</button>
        </div>
      </div>
    </div>
  );
}
