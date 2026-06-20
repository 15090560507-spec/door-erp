"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { generateRender, type RenderImageResult } from "@/lib/renderApi";

const CONFIG_KEY = "door_render_config_v1";
const DEFAULT_PROMPT = "??????????????????????????????????????????????????";

interface RenderConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
  count: number;
}

const defaultConfig: RenderConfig = { baseUrl: "", apiKey: "", model: "", count: 1 };

export default function RenderPage() {
  const [config, setConfig] = useState<RenderConfig>(defaultConfig);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [lineArt, setLineArt] = useState<File | null>(null);
  const [reference, setReference] = useState<File | null>(null);
  const [lineArtPreview, setLineArtPreview] = useState("");
  const [referencePreview, setReferencePreview] = useState("");
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [size, setSize] = useState("1k");
  const [results, setResults] = useState<RenderImageResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"" | "success" | "error">("");

  useEffect(() => {
    const raw = localStorage.getItem(CONFIG_KEY);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw) as Partial<RenderConfig>;
      setConfig({ baseUrl: saved.baseUrl || "", apiKey: saved.apiKey || "", model: saved.model || "", count: clampCount(saved.count) });
    } catch {
      localStorage.removeItem(CONFIG_KEY);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
  }, [config]);

  useEffect(() => () => {
    if (lineArtPreview) URL.revokeObjectURL(lineArtPreview);
    if (referencePreview) URL.revokeObjectURL(referencePreview);
  }, [lineArtPreview, referencePreview]);

  const activeResult = results[activeIndex] || null;
  const canGenerate = Boolean(lineArt && reference && config.baseUrl.trim() && config.apiKey.trim() && config.model.trim() && prompt.trim());

  function updateConfig<K extends keyof RenderConfig>(key: K, value: RenderConfig[K]) {
    setConfig((current) => ({ ...current, [key]: value }));
  }

  function pickFile(event: ChangeEvent<HTMLInputElement>, type: "line" | "reference") {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) return showMessage("???????", "error");
    const url = URL.createObjectURL(file);
    if (type === "line") {
      if (lineArtPreview) URL.revokeObjectURL(lineArtPreview);
      setLineArt(file);
      setLineArtPreview(url);
    } else {
      if (referencePreview) URL.revokeObjectURL(referencePreview);
      setReference(file);
      setReferencePreview(url);
    }
    showMessage(`${file.name} ???`, "success");
  }

  function clearFile(type: "line" | "reference") {
    if (type === "line") {
      if (lineArtPreview) URL.revokeObjectURL(lineArtPreview);
      setLineArt(null);
      setLineArtPreview("");
    } else {
      if (referencePreview) URL.revokeObjectURL(referencePreview);
      setReference(null);
      setReferencePreview("");
    }
  }

  async function handleGenerate() {
    if (!lineArt) return showMessage("???????", "error");
    if (!reference) return showMessage("???????", "error");
    if (!config.baseUrl.trim()) return showMessage("??? Base URL", "error");
    if (!config.apiKey.trim()) return showMessage("??? API Key", "error");
    if (!config.model.trim()) return showMessage("??? Model", "error");
    if (!prompt.trim()) return showMessage("??? Prompt", "error");

    setLoading(true);
    setResults([]);
    setActiveIndex(0);
    showMessage("???????...", "");
    try {
      const data = await generateRender({ lineArt, reference, baseUrl: config.baseUrl, apiKey: config.apiKey, model: config.model, prompt, size, count: config.count });
      setResults(data.images || []);
      showMessage(`?????? ${data.images?.length || 0} ?`, "success");
    } catch (error: unknown) {
      const err = error as { userMessage?: string; response?: { data?: { detail?: string } }; message?: string };
      showMessage(err.userMessage || err.response?.data?.detail || err.message || "??????", "error");
    } finally {
      setLoading(false);
    }
  }

  function downloadActive() {
    if (!activeResult) return;
    const link = document.createElement("a");
    link.href = activeResult.src;
    link.download = `????-${activeIndex + 1}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function resetAll() {
    clearFile("line");
    clearFile("reference");
    setPrompt(DEFAULT_PROMPT);
    setSize("1k");
    setResults([]);
    setActiveIndex(0);
    showMessage("????????????????", "");
  }

  function showMessage(text: string, type: "" | "success" | "error") {
    setMessage(text);
    setMessageType(type);
  }

  const statusClass = useMemo(() => {
    if (messageType === "error") return "bg-[#FF3B30]/10 text-[#FF3B30]";
    if (messageType === "success") return "bg-[#34C759]/10 text-[#34C759]";
    return "bg-[#007AFF]/10 text-[#007AFF]";
  }, [messageType]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[18px] font-semibold text-[#1C1C1E]">????</h1>
          <p className="text-[12px] text-[#8E8E93] mt-1">?????????????????</p>
        </div>
        {message && <span className={`text-[12px] px-3 py-1 rounded-full font-medium ${statusClass}`}>{message}</span>}
      </div>

      <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 overflow-hidden">
        <button type="button" onClick={() => setSettingsOpen((open) => !open)} className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-[#F2F2F7] transition-colors">
          <span className="text-[14px] font-semibold text-[#1C1C1E]">????</span>
          <span className="text-[12px] text-[#8E8E93]">{settingsOpen ? "??" : "??"}</span>
        </button>
        {settingsOpen && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 px-5 pb-5 border-t border-[#E5E5EA]/60 pt-4">
            <TextField label="Base URL" value={config.baseUrl} onChange={(value) => updateConfig("baseUrl", value)} placeholder="https://api.example.com/v1" />
            <TextField label="API Key" type="password" value={config.apiKey} onChange={(value) => updateConfig("apiKey", value)} placeholder="sk-..." />
            <TextField label="Model" value={config.model} onChange={(value) => updateConfig("model", value)} placeholder="image-edit-model" />
            <label className="block">
              <span className="text-[12px] font-medium text-[#8E8E93]">Count</span>
              <input type="number" min={1} max={4} value={config.count} onChange={(event) => updateConfig("count", clampCount(event.target.value))} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
            </label>
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <UploadPanel title="????" kicker="Line Art" preview={lineArtPreview} fileName={lineArt?.name} onPick={(event) => pickFile(event, "line")} onClear={() => clearFile("line")} />
        <UploadPanel title="????" kicker="Reference" preview={referencePreview} fileName={reference?.name} onPick={(event) => pickFile(event, "reference")} onClear={() => clearFile("reference")} />
        <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4 min-h-[320px] flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-[11px] font-semibold text-[#007AFF] uppercase">Result</p>
              <h2 className="text-[15px] font-semibold text-[#1C1C1E]">????</h2>
            </div>
            <button type="button" onClick={downloadActive} disabled={!activeResult} className="px-3 py-1.5 text-[12px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] disabled:opacity-50 hover:bg-[#E5E5EA]/70 transition-colors">??</button>
          </div>
          <div className="flex-1 min-h-[240px] rounded-xl bg-[#F2F2F7] border border-[#E5E5EA]/60 flex items-center justify-center overflow-hidden">
            {loading ? <div className="text-center text-[#8E8E93] text-[13px]"><div className="w-8 h-8 mx-auto mb-3 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />????...</div> : activeResult ? <img src={activeResult.src} alt={`?????? ${activeIndex + 1}`} className="max-w-full max-h-[520px] object-contain" /> : <p className="text-[13px] text-[#8E8E93]">?????????????</p>}
          </div>
          {results.length > 1 && <div className="flex gap-2 mt-3 overflow-x-auto">{results.map((image, index) => <button key={`${image.src.slice(0, 32)}-${index}`} type="button" onClick={() => setActiveIndex(index)} className={`w-16 h-16 rounded-lg border overflow-hidden shrink-0 ${index === activeIndex ? "border-[#007AFF]" : "border-[#E5E5EA]"}`}><img src={image.src} alt={`?? ${index + 1}`} className="w-full h-full object-cover" /></button>)}</div>}
        </section>
      </div>

      <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-[160px_1fr] gap-3">
          <label className="block"><span className="text-[12px] font-medium text-[#8E8E93]">Size</span><select value={size} onChange={(event) => setSize(event.target.value)} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none bg-white"><option value="1k">1K</option><option value="2k">2K</option><option value="4k">4K</option></select></label>
          <label className="block"><span className="text-[12px] font-medium text-[#8E8E93]">Prompt</span><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none resize-y" /></label>
        </div>
        <div className="flex gap-2 justify-end">
          <button type="button" onClick={resetAll} disabled={loading} className="px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/70 disabled:opacity-50 transition-colors">??</button>
          <button type="button" onClick={handleGenerate} disabled={!canGenerate || loading} className="px-5 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 disabled:opacity-50 transition-colors">{loading ? "???..." : "?????"}</button>
        </div>
      </section>
    </div>
  );
}

function TextField({ label, value, onChange, placeholder, type = "text" }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; type?: string }) {
  return <label className="block"><span className="text-[12px] font-medium text-[#8E8E93]">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" /></label>;
}

function UploadPanel({ title, kicker, preview, fileName, onPick, onClear }: { title: string; kicker: string; preview: string; fileName?: string; onPick: (event: ChangeEvent<HTMLInputElement>) => void; onClear: () => void }) {
  return <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4 min-h-[320px] flex flex-col"><div className="flex items-center justify-between mb-3"><div><p className="text-[11px] font-semibold text-[#007AFF] uppercase">{kicker}</p><h2 className="text-[15px] font-semibold text-[#1C1C1E]">{title}</h2></div><button type="button" onClick={onClear} className="w-8 h-8 rounded-lg text-[#8E8E93] hover:text-[#1C1C1E] hover:bg-[#F2F2F7] transition-colors" aria-label={`??${title}`}>?</button></div><label className="flex-1 min-h-[240px] rounded-xl border border-dashed border-[#C7C7CC] bg-[#F2F2F7] hover:bg-[#E5E5EA]/50 transition-colors cursor-pointer overflow-hidden flex items-center justify-center"><input type="file" accept="image/*" onChange={onPick} className="hidden" />{preview ? <img src={preview} alt={`${title}??`} className="w-full h-full object-contain" /> : <span className="text-center text-[13px] text-[#8E8E93]">????{title}<br /><span className="text-[12px]">?? PNG?JPG?WEBP</span></span>}</label>{fileName && <p className="text-[12px] text-[#8E8E93] mt-2 truncate">{fileName}</p>}</section>;
}

function clampCount(value: unknown): number {
  const parsed = Number.parseInt(String(value ?? 1), 10);
  if (Number.isNaN(parsed)) return 1;
  return Math.min(Math.max(parsed, 1), 4);
}
