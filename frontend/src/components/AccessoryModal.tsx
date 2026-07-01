"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { createAccessory, deleteAccessory, getAccessories, exportAccessories, importAccessories, importAccessoriesXlsx } from "@/lib/quoteApi";
import type { Accessory } from "@/lib/quoteTypes";
import { UNIT_OPTIONS } from "@/lib/quoteTypes";

interface Props {
  open: boolean;
  onClose: () => void;
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export default function AccessoryModal({ open, onClose }: Props) {
  const [accessories, setAccessories] = useState<Accessory[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [model, setModel] = useState("");
  const [keywords, setKeywords] = useState("");
  const [unit, setUnit] = useState("m2");
  const [unitPrice, setUnitPrice] = useState("");
  const [remark, setRemark] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async (q?: string) => {
    try {
      const data = await getAccessories(q);
      setAccessories(data);
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    if (open) load(search);
  }, [open, load]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => load(search), 250);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search, load, open]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setStatus("请填写配件名称");
      return;
    }
    setSubmitting(true);
    setStatus("");
    try {
      await createAccessory({
        name: name.trim(),
        category: category.trim(),
        model: model.trim(),
        keywords: keywords.trim(),
        unit: unit.trim() || "m2",
        unitPrice: unitPrice ? Number(unitPrice) : undefined,
        remark: remark.trim(),
      });
      setName(""); setCategory(""); setModel(""); setKeywords("");
      setUnit("m2"); setUnitPrice(""); setRemark("");
      setStatus("配件已添加");
      await load(search);
    } catch (err: any) {
      setStatus(err?.userMessage || err?.message || "添加失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteAccessory(id);
      setStatus("配件已删除");
      await load(search);
    } catch (err: any) {
      setStatus(err?.userMessage || err?.message || "删除失败");
    }
  }

  async function handleExport() {
    try {
      const data = await exportAccessories();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `配件库_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus(`已导出 ${data.length} 条配件`);
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
        setStatus(`成功导入/更新 ${result.imported} 条价格库数据`);
        setSearch("");
        await load();
        e.target.value = "";
        return;
      }
      const text = await file.text();
      const json = JSON.parse(text);
      const items = Array.isArray(json) ? json : json.accessories;
      if (!Array.isArray(items) || !items.length) {
        setStatus("文件中没有有效的配件数据");
        return;
      }
      const result = await importAccessories(items);
      setStatus(`成功导入 ${result.imported} 条配件`);
      setSearch("");
      await load();
    } catch (err: any) {
      setStatus(err?.userMessage || "导入失败，请检查文件格式");
    }
    e.target.value = "";
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E5E5EA]/60">
          <h3 className="text-[16px] font-semibold text-[#1C1C1E]">配件库</h3>
          <button onClick={onClose} className="text-[#8E8E93] hover:text-[#1C1C1E] text-[20px] leading-none transition-colors">&times;</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Add Form */}
          <form onSubmit={handleAdd} className="grid grid-cols-3 gap-3">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="配件名称 *" required className="col-span-3 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="类别" className="px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="型号" className="px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            <input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="关键词" className="px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="单位" list="modalUnitOptions" className="px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            <input value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} type="number" step="0.01" placeholder="单价" className="px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            <input value={remark} onChange={(e) => setRemark(e.target.value)} placeholder="备注" className="col-span-3 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            <datalist id="modalUnitOptions">
              {UNIT_OPTIONS.map((u) => <option key={u} value={u} />)}
            </datalist>
            <div className="col-span-3 flex items-center gap-3">
              <button type="submit" disabled={submitting} className="px-5 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 disabled:opacity-50 transition-colors">
                {submitting ? "添加中..." : "添加配件"}
              </button>
              {status && <span className="text-[12px] text-[#8E8E93]">{status}</span>}
            </div>
          </form>

          {/* Search + Import/Export */}
          <div className="flex gap-3 items-center">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索配件（名称/类别/型号/关键词）"
              className="flex-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
            />
            <button onClick={handleExport} type="button" className="px-3 py-2 text-[12px] font-medium rounded-lg border border-[#E5E5EA]/60 text-[#1C1C1E] hover:bg-[#F2F2F7] transition-colors whitespace-nowrap">导出</button>
            <label className="px-3 py-2 text-[12px] font-medium rounded-lg border border-[#E5E5EA]/60 text-[#1C1C1E] hover:bg-[#F2F2F7] transition-colors cursor-pointer whitespace-nowrap">
              导入
              <input type="file" accept=".json,.xlsx,.xlsm" onChange={handleImport} className="hidden" />
            </label>
          </div>

          {/* List */}
          <div className="space-y-1">
            {accessories.length === 0 ? (
              <p className="text-[13px] text-[#8E8E93] text-center py-6">暂无配件</p>
            ) : (
              accessories.map((acc) => (
                <div key={acc.id} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-[#F2F2F7]/50 transition-colors group">
                  <div className="flex-1 min-w-0">
                    <span className="text-[13px] font-medium text-[#1C1C1E]">{escapeHtml(acc.name)}</span>
                    <span className="ml-2 text-[11px] text-[#8E8E93]">
                      {acc.category || "未分类"} / {acc.model || "-"} / {acc.unit || "m2"} / ¥{acc.unitPrice ?? 0}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDelete(acc.id)}
                    className="text-[11px] text-[#FF3B30]/60 hover:text-[#FF3B30] opacity-0 group-hover:opacity-100 transition-all px-2 py-1"
                  >
                    删除
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
