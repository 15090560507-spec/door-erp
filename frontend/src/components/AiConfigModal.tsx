"use client";

import { useEffect, useRef, useState } from "react";
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
  const [status, setStatus] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [loadVersion, setLoadVersion] = useState(0);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  }, []);

  useEffect(() => {
    if (!open) return;
    let active = true;
    (async () => {
      try {
        const data = await getAiConfig();
        if (!active) return;
        setConfig({ ...data, apiKey: "" });
        setLoaded(true);
        setStatus(null);
      } catch (error) {
        if (active) setStatus({ tone: "error", message: errorMessage(error, "读取配置失败") });
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [open, loadVersion]);

  async function handleSave() {
    if (!loaded || loading || saving || status?.tone === "success") return;
    setSaving(true);
    setStatus(null);
    try {
      const updated = await updateAiConfig({
        baseUrl: config.baseUrl,
        endpointPath: config.endpointPath,
        apiKey: config.apiKey,
        model: config.model,
        prompt: config.prompt,
      });
      setConfig({ ...updated, apiKey: "" });
      setStatus({ tone: "success", message: "AI 配置已保存" });
      closeTimer.current = setTimeout(() => onClose(), 800);
    } catch (err: unknown) {
      setStatus({ tone: "error", message: errorMessage(err, "保存失败") });
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <div className="ui-dialog-backdrop" onClick={() => { if (!saving) onClose(); }}>
      <div
        className="ui-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="ui-dialog__header">
          <div>
            <h3 className="ui-dialog__title">AI 模型配置</h3>
            <p className="ui-dialog__description">配置报价识别所使用的模型连接与提示词。</p>
          </div>
          <button onClick={onClose} disabled={saving} className="ui-dialog__close" aria-label="关闭">
            <X size={18} />
          </button>
        </div>

        <div className="ui-dialog__body">
          {loading && <p role="status" className="mb-3 text-sm text-[#62626B]">正在读取配置…</p>}
          <fieldset disabled={loading || !loaded || saving} className="min-w-0 space-y-4 border-0 p-0 disabled:opacity-60">
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
          </fieldset>
        </div>

        <div className="ui-dialog__footer flex-wrap justify-between">
          {status ? (
            <span role={status.tone === "error" ? "alert" : "status"} className={`min-w-0 w-full break-words text-[13px] sm:w-auto ${status.tone === "error" ? "text-[#C93531]" : "text-[#248A3D]"}`}>{status.message}</span>
          ) : (
            <span />
          )}
          <div className="flex w-full shrink-0 flex-wrap gap-2 sm:w-auto [&_button]:whitespace-nowrap">
            {!loaded && !loading && <button type="button" onClick={() => { setStatus(null); setLoading(true); setLoadVersion(value => value + 1); }} className="ui-button ui-button--secondary">重新读取</button>}
            <button onClick={onClose} disabled={saving} className="ui-button ui-button--secondary">
              取消
            </button>
            <button onClick={handleSave} disabled={saving || loading || !loaded || status?.tone === "success"} className="ui-button ui-button--primary">
              {saving ? "保存中..." : "保存 AI 配置"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function errorMessage(error: unknown, fallback: string) {
  const value = error as { userMessage?: string; message?: string };
  return value?.userMessage || value?.message || fallback;
}
