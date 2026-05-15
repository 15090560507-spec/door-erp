"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

const KEY_LABELS: Record<string, string> = {
  DOOR_TYPES: "门型",
  KX_OPTIONS: "开向",
  NK_OPTIONS: "内外开",
  MATERIALS: "制作材料",
  HANDLES: "拉手",
  LOCKS: "锁体",
  HINGES: "合页",
  COLOR_PRESETS: "颜色",
  THRESHOLD_OPTIONS: "下槛方案",
  QC_OPTIONS: "气窗",
  BZ_OPTIONS: "包装",
  HYSL_OPTIONS: "合页数量",
};

export default function DropdownOptionsManager() {
  const [options, setOptions] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.get("/admin/dropdown-options")
      .then(({ data }) => setOptions(data.options || {}))
      .catch(() => setMsg("加载下拉选项失败"))
      .finally(() => setLoading(false));
  }, []);

  const addItem = (key: string) => {
    setOptions((prev) => {
      const list = [...(prev[key] || []), ""];
      return { ...prev, [key]: list };
    });
  };

  const updateItem = (key: string, idx: number, value: string) => {
    setOptions((prev) => {
      const list = [...prev[key]];
      list[idx] = value;
      return { ...prev, [key]: list };
    });
  };

  const removeItem = (key: string, idx: number) => {
    setOptions((prev) => {
      const list = prev[key].filter((_, i) => i !== idx);
      return { ...prev, [key]: list };
    });
  };

  const save = async () => {
    setSaving(true);
    setMsg("");
    try {
      // 过滤空值
      const cleaned: Record<string, string[]> = {};
      for (const [k, v] of Object.entries(options)) {
        cleaned[k] = v.filter((s) => s.trim() !== "");
        if (cleaned[k].length === 0) delete cleaned[k];
      }
      const { data } = await api.put("/admin/dropdown-options", cleaned);
      setOptions(data.options || {});
      setMsg("保存成功 ✓");
    } catch {
      setMsg("保存失败，请重试");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6 mb-6">
        <p className="text-sm text-gray-400">加载下拉选项配置...</p>
      </div>
    );
  }

  const keys = Object.keys(options);

  return (
    <div className="bg-white rounded-2xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-[#1C1C1E]">下拉选项管理</h3>
          <p className="text-[13px] text-[#8E8E93] mt-0.5">
            自定义表单中的下拉选项，保存后即时生效
          </p>
        </div>
        <button
          onClick={save}
          disabled={saving}
          className="px-5 py-2 text-sm font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#0062CC] disabled:opacity-50 transition-colors"
        >
          {saving ? "保存中..." : "保存全部"}
        </button>
      </div>

      {msg && (
        <p
          className={`text-sm mb-4 px-3 py-2 rounded-md ${
            msg.includes("失败") ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"
          }`}
        >
          {msg}
        </p>
      )}

      {keys.length === 0 ? (
        <p className="text-sm text-gray-400">暂无下拉选项配置</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {keys.map((key) => {
            const items = options[key] || [];
            return (
              <div key={key} className="border border-[#F2F2F7] rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[13px] font-semibold text-[#1C1C1E]">
                    {KEY_LABELS[key] || key}
                  </span>
                  <button
                    onClick={() => addItem(key)}
                    className="text-xs px-2 py-0.5 rounded bg-[#F2F2F7] text-[#007AFF] hover:bg-[#E5E5EA] transition-colors"
                  >
                    + 添加
                  </button>
                </div>
                <div className="space-y-1.5">
                  {items.map((val, idx) => (
                    <div key={idx} className="flex items-center gap-1">
                      <input
                        type="text"
                        value={val}
                        onChange={(e) => updateItem(key, idx, e.target.value)}
                        className="flex-1 px-2 py-1 text-xs rounded border border-[#C7C7CC] outline-none focus:border-[#007AFF] transition-colors"
                      />
                      <button
                        onClick={() => removeItem(key, idx)}
                        className="text-[#FF3B30] text-xs px-1 hover:bg-red-50 rounded transition-colors"
                        title="删除"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  {items.length === 0 && (
                    <p className="text-xs text-gray-300 italic">暂无选项</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
