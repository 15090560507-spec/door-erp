"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
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
    hasApiKey: false,
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
        setConfig({ ...data, apiKey: "" });
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
      setConfig({ ...updated, apiKey: "" });
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
    <div className="ui-dialog-backdrop" onClick={onClose}>
      <div
        className="ui-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="ui-dialog__header">
          <div>
            <h3 className="ui-dialog__title">AI 模型配置</h3>
            <p className="ui-dialog__description">配置报价识别所使用的模型连接与提示词。</p>
          </div>
          <button onClick={onClose} className="ui-dialog__close" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="ui-dialog__body space-y-4">
          <label className="block">
            <span className="text-[13px] font-medium text-[#62626B]">Base URL</span>
            <input
              type="text"
              value={config.baseUrl}
              onChange={(event) => setConfig({ ...config, baseUrl: event.target.value })}
              placeholder="https://api.moonshot.cn/v1"
              className="mt-1 w-full border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[13px] font-medium text-[#62626B]">Endpoint Path</span>
            <input
              type="text"
              value={config.endpointPath}
              onChange={(event) => setConfig({ ...config, endpointPath: event.target.value })}
              placeholder="/chat/completions"
              className="mt-1 w-full border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[13px] font-medium text-[#62626B]">模型名</span>
            <input
              type="text"
              value={config.model}
              onChange={(event) => setConfig({ ...config, model: event.target.value })}
              placeholder="moonshot-v1-8k-vision-preview"
              className="mt-1 w-full border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[13px] font-medium text-[#62626B]">API Key</span>
            <input
              type="password"
              value={config.apiKey || ""}
              onChange={(event) => setConfig({ ...config, apiKey: event.target.value })}
              placeholder={config.hasApiKey ? "API Key 已保存，留空则不修改" : "粘贴你的 API Key"}
              className="mt-1 w-full border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[13px] font-medium text-[#62626B]">识别提示词</span>
            <textarea
              value={config.prompt}
              onChange={(event) => setConfig({ ...config, prompt: event.target.value })}
              rows={8}
              className="mt-1 w-full resize-y border border-[#D7D7DE] px-3 py-2 text-sm focus:border-[#007AFF] focus:outline-none"
            />
          </label>
        </div>

        <div className="ui-dialog__footer justify-between">
          {status ? (
            <span className={`text-[13px] ${status.includes("失败") ? "text-[#C93531]" : "text-[#248A3D]"}`}>{status}</span>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button onClick={onClose} className="ui-button ui-button--secondary">
              取消
            </button>
            <button onClick={handleSave} disabled={saving} className="ui-button ui-button--primary">
              {saving ? "保存中..." : "保存 AI 配置"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
