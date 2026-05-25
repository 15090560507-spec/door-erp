"use client";

import { useEffect, useState } from "react";
import { getAiConfig, updateAiConfig } from "@/lib/quoteApi";
import type { AiConfig } from "@/lib/quoteTypes";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function AiConfigModal({ open, onClose }: Props) {
  const [config, setConfig] = useState<AiConfig>({
    baseUrl: "",
    endpointPath: "/chat/completions",
    apiKey: "",
    model: "",
    prompt: "",
    updatedAt: "",
  });
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const data = await getAiConfig();
        setConfig(data);
      } catch {
        // keep local defaults
      }
    })();
  }, [open]);

  async function handleSave() {
    setSaving(true);
    setStatus("");
    try {
      const updated = await updateAiConfig({
        baseUrl: config.baseUrl,
        endpointPath: config.endpointPath,
        apiKey: config.apiKey,
        model: config.model,
        prompt: config.prompt,
      });
      setConfig(updated);
      setStatus("AI 配置已保存");
      setTimeout(() => onClose(), 800);
    } catch (err: unknown) {
      const error = err as { userMessage?: string; message?: string };
      setStatus(error?.userMessage || error?.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col mx-4"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E5E5EA]/60">
          <h3 className="text-[16px] font-semibold text-[#1C1C1E]">AI 模型配置</h3>
          <button onClick={onClose} className="text-[#8E8E93] hover:text-[#1C1C1E] text-[20px] leading-none transition-colors">
            &times;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          <label className="block">
            <span className="text-[12px] font-medium text-[#8E8E93]">Base URL</span>
            <input
              type="text"
              value={config.baseUrl}
              onChange={(event) => setConfig({ ...config, baseUrl: event.target.value })}
              placeholder="https://api.moonshot.cn/v1"
              className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[12px] font-medium text-[#8E8E93]">Endpoint Path</span>
            <input
              type="text"
              value={config.endpointPath}
              onChange={(event) => setConfig({ ...config, endpointPath: event.target.value })}
              placeholder="/chat/completions"
              className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[12px] font-medium text-[#8E8E93]">模型名</span>
            <input
              type="text"
              value={config.model}
              onChange={(event) => setConfig({ ...config, model: event.target.value })}
              placeholder="moonshot-v1-8k-vision-preview"
              className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[12px] font-medium text-[#8E8E93]">API Key</span>
            <input
              type="password"
              value={config.apiKey}
              onChange={(event) => setConfig({ ...config, apiKey: event.target.value })}
              placeholder="粘贴你的 API Key"
              className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[12px] font-medium text-[#8E8E93]">识别提示词</span>
            <textarea
              value={config.prompt}
              onChange={(event) => setConfig({ ...config, prompt: event.target.value })}
              rows={8}
              className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none resize-y"
            />
          </label>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-[#E5E5EA]/60">
          {status ? (
            <span className={`text-[12px] ${status.includes("失败") ? "text-[#FF3B30]" : "text-[#34C759]"}`}>{status}</span>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/60 transition-colors">
              取消
            </button>
            <button onClick={handleSave} disabled={saving} className="px-5 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 disabled:opacity-50 transition-colors">
              {saving ? "保存中..." : "保存 AI 配置"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
