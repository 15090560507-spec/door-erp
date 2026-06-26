
"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { generateRender, type RenderImageResult } from "@/lib/renderApi";

const CONFIG_KEY = "door_render_config_v1";
const LIBRARY_KEY = "door_render_reference_library_v1";

const PART_OPTIONS = ["\u6b3e\u5f0f", "\u62c9\u624b", "\u82b1\u4ef6", "\u989c\u8272", "\u5408\u9875"];
const DEFAULT_REFERENCE_LABELS = ["\u6b3e\u5f0f", "\u62c9\u624b", "\u82b1\u4ef6", "\u5408\u9875"];

const T = {
  defaultPrompt: "\u57fa\u4e8e\u7ebf\u7a3f\u7ed3\u6784\u751f\u6210\u95e8\u4e1a\u6548\u679c\u56fe\uff0c\u4fdd\u7559\u95e8\u578b\u6bd4\u4f8b\u548c\u4e3b\u8981\u7ebf\u6761\uff0c\u53c2\u8003\u56fe\u6309\u5bf9\u5e94\u6587\u672c\u4ec5\u7528\u4e8e\u76f8\u5e94\u90e8\u4ef6\u3001\u6750\u8d28\u3001\u989c\u8272\u548c\u6c1b\u56f4\uff0c\u771f\u5b9e\u4ea7\u54c1\u6e32\u67d3\u98ce\u683c\u3002",
  uploadImageOnly: "\u8bf7\u4e0a\u4f20\u56fe\u7247\u6587\u4ef6",
  loaded: "\u5df2\u8f7d\u5165",
  uploadLineFirst: "\u8bf7\u5148\u4e0a\u4f20\u7ebf\u7a3f\u56fe",
  uploadReferenceFirst: "\u8bf7\u81f3\u5c11\u4e0a\u4f20\u4e00\u5f20\u53c2\u8003\u56fe",
  fill: "\u8bf7\u586b\u5199",
  generating: "\u6b63\u5728\u751f\u6210\u6548\u679c\u56fe...",
  generatedPrefix: "\u751f\u6210\u5b8c\u6210\uff0c\u5171",
  generatedSuffix: "\u5f20",
  failed: "\u6548\u679c\u6e32\u67d3\u5931\u8d25",
  filenamePrefix: "\u6548\u679c\u6e32\u67d3",
  resetKeptConfig: "\u5df2\u6e05\u7a7a\u4e0a\u4f20\u548c\u7ed3\u679c\uff0c\u6a21\u578b\u914d\u7f6e\u548c\u5e38\u7528\u5e93\u5df2\u4fdd\u7559",
  title: "\u6548\u679c\u6e32\u67d3",
  subtitle: "\u4e0a\u4f20\u7ebf\u7a3f\uff0c\u4e3a\u6b3e\u5f0f\u3001\u62c9\u624b\u3001\u82b1\u4ef6\u7b49\u914d\u4ef6\u5206\u522b\u6dfb\u52a0\u53c2\u8003\u56fe\u3002",
  configTitle: "\u6a21\u578b\u914d\u7f6e",
  libraryTitle: "\u6211\u7684\u5e38\u7528\u53c2\u8003\u5e93",
  collapse: "\u6536\u8d77",
  expand: "\u5c55\u5f00",
  lineArtTitle: "\u7ebf\u7a3f\u56fe\u7eb8",
  referencesTitle: "\u53c2\u8003\u56fe\u7eb8",
  resultTitle: "\u751f\u6210\u7ed3\u679c",
  download: "\u4e0b\u8f7d",
  resultAlt: "\u6548\u679c\u6e32\u67d3\u7ed3\u679c",
  emptyResult: "\u751f\u6210\u540e\u7684\u6548\u679c\u56fe\u4f1a\u663e\u793a\u5728\u8fd9\u91cc",
  resultThumb: "\u7ed3\u679c",
  clear: "\u6e05\u7a7a",
  generate: "\u751f\u6210\u6548\u679c\u56fe",
  generatingShort: "\u751f\u6210\u4e2d...",
  clickUpload: "\u70b9\u51fb\u4e0a\u4f20",
  support: "\u652f\u6301 PNG\u3001JPG\u3001WEBP",
  clearPrefix: "\u6e05\u7a7a",
  preview: "\u9884\u89c8",
  addReference: "\u6dfb\u52a0\u53c2\u8003\u9879",
  remove: "\u5220\u9664",
  saveToLibrary: "\u4fdd\u5b58\u5230\u5e38\u7528\u5e93",
  savedToLibrary: "\u5df2\u4fdd\u5b58\u5230\u5e38\u7528\u5e93",
  uploadToLibrary: "上传到常用库",
  libraryCategory: "分类",
  batchUploadLibrary: "批量上传参考图",
  chooseFromLibrary: "\u4ece\u5e93\u9009\u62e9",
  noLibrary: "\u5e38\u7528\u5e93\u6682\u65e0\u56fe\u7247",
  partLabel: "\u53c2\u8003\u5185\u5bb9",
  imageLabel: "\u53c2\u8003\u56fe",
  customPart: "\u8f93\u5165\u6216\u9009\u62e9\u914d\u4ef6\u7c7b\u578b",
};

interface RenderConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
  count: number;
}

interface ReferenceRow {
  id: string;
  label: string;
  file: File | null;
  preview: string;
  fileName: string;
}

interface LibraryItem {
  id: string;
  label: string;
  name: string;
  dataUrl: string;
  createdAt: number;
}

const defaultConfig: RenderConfig = { baseUrl: "", apiKey: "", model: "", count: 1 };

export default function RenderPage() {
  const [config, setConfig] = useState<RenderConfig>(defaultConfig);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [libraryUploadLabel, setLibraryUploadLabel] = useState(PART_OPTIONS[0]);
  const [lineArt, setLineArt] = useState<File | null>(null);
  const [lineArtPreview, setLineArtPreview] = useState("");
  const [references, setReferences] = useState<ReferenceRow[]>(() => defaultReferenceRows());
  const [prompt, setPrompt] = useState(T.defaultPrompt);
  const [size, setSize] = useState("1k");
  const [results, setResults] = useState<RenderImageResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState<"" | "success" | "error">("");

  useEffect(() => {
    const raw = localStorage.getItem(CONFIG_KEY);
    if (raw) {
      try {
        const saved = JSON.parse(raw) as Partial<RenderConfig>;
        setConfig({ baseUrl: saved.baseUrl || "", apiKey: saved.apiKey || "", model: saved.model || "", count: clampCount(saved.count) });
      } catch {
        localStorage.removeItem(CONFIG_KEY);
      }
    }

    const rawLibrary = localStorage.getItem(LIBRARY_KEY);
    if (rawLibrary) {
      try {
        const savedLibrary = JSON.parse(rawLibrary) as LibraryItem[];
        setLibrary(Array.isArray(savedLibrary) ? savedLibrary.filter((item) => item?.dataUrl) : []);
      } catch {
        localStorage.removeItem(LIBRARY_KEY);
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
  }, [config]);

  useEffect(() => {
    localStorage.setItem(LIBRARY_KEY, JSON.stringify(library));
  }, [library]);

  useEffect(() => () => {
    revokePreview(lineArtPreview);
    references.forEach((row) => revokePreview(row.preview));
  }, [lineArtPreview, references]);

  const activeResult = results[activeIndex] || null;
  const selectedReferences = references.filter((row) => row.preview);
  const canGenerate = Boolean(lineArt && selectedReferences.length > 0 && config.baseUrl.trim() && config.apiKey.trim() && config.model.trim() && prompt.trim());

  function updateConfig<K extends keyof RenderConfig>(key: K, value: RenderConfig[K]) {
    setConfig((current) => ({ ...current, [key]: value }));
  }

  function pickLineArt(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) return showMessage(T.uploadImageOnly, "error");
    const url = URL.createObjectURL(file);
    revokePreview(lineArtPreview);
    setLineArt(file);
    setLineArtPreview(url);
    showMessage(`${file.name} ${T.loaded}`, "success");
  }

  function pickReference(rowId: string, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) return showMessage(T.uploadImageOnly, "error");
    const url = URL.createObjectURL(file);
    setReferences((current) => current.map((row) => {
      if (row.id !== rowId) return row;
      revokePreview(row.preview);
      return { ...row, file, preview: url, fileName: file.name };
    }));
    showMessage(`${file.name} ${T.loaded}`, "success");
  }

  function updateReference(rowId: string, patch: Partial<ReferenceRow>) {
    setReferences((current) => current.map((row) => (row.id === rowId ? { ...row, ...patch } : row)));
  }

  function clearReference(rowId: string) {
    setReferences((current) => current.map((row) => {
      if (row.id !== rowId) return row;
      revokePreview(row.preview);
      return { ...row, file: null, preview: "", fileName: "" };
    }));
  }

  function addReference() {
    setReferences((current) => [...current, newReferenceRow("")]);
  }

  function removeReference(rowId: string) {
    setReferences((current) => {
      const target = current.find((row) => row.id === rowId);
      if (target) revokePreview(target.preview);
      const next = current.filter((row) => row.id !== rowId);
      return next.length ? next : [newReferenceRow("")];
    });
  }

  async function saveReferenceToLibrary(row: ReferenceRow) {
    if (!row.preview) return showMessage(T.uploadReferenceFirst, "error");
    const dataUrl = row.file ? await readFileAsDataUrl(row.file) : row.preview;
    const item: LibraryItem = {
      id: createId(),
      label: row.label.trim() || T.imageLabel,
      name: row.fileName || `${row.label || T.imageLabel}.png`,
      dataUrl,
      createdAt: Date.now(),
    };
    setLibrary((current) => [item, ...current]);
    showMessage(T.savedToLibrary, "success");
  }

  async function uploadLibraryFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    const imageFiles = files.filter((file) => file.type.startsWith("image/"));
    if (!imageFiles.length) return showMessage(T.uploadImageOnly, "error");
    const items = await Promise.all(imageFiles.map(async (file) => ({
      id: createId(),
      label: libraryUploadLabel.trim() || T.imageLabel,
      name: file.name,
      dataUrl: await readFileAsDataUrl(file),
      createdAt: Date.now(),
    })));
    setLibrary((current) => [...items, ...current]);
    showMessage(`${T.savedToLibrary} ${items.length} ${T.generatedSuffix}`, "success");
  }

  function applyLibraryItem(rowId: string, itemId: string) {
    const item = library.find((entry) => entry.id === itemId);
    if (!item) return;
    setReferences((current) => current.map((row) => {
      if (row.id !== rowId) return row;
      revokePreview(row.preview);
      return { ...row, label: row.label || item.label, file: null, preview: item.dataUrl, fileName: item.name };
    }));
    showMessage(`${item.name} ${T.loaded}`, "success");
  }

  function removeLibraryItem(itemId: string) {
    setLibrary((current) => current.filter((item) => item.id !== itemId));
  }

  async function handleGenerate() {
    if (!lineArt) return showMessage(T.uploadLineFirst, "error");
    if (!selectedReferences.length) return showMessage(T.uploadReferenceFirst, "error");
    if (!config.baseUrl.trim()) return showMessage(`${T.fill} Base URL`, "error");
    if (!config.apiKey.trim()) return showMessage(`${T.fill} API Key`, "error");
    if (!config.model.trim()) return showMessage(`${T.fill} Model`, "error");
    if (!prompt.trim()) return showMessage(`${T.fill} Prompt`, "error");

    setLoading(true);
    setResults([]);
    setActiveIndex(0);
    showMessage(T.generating, "");
    try {
      const referenceFiles = selectedReferences.map((row, index) => ({
        label: row.label.trim() || `${T.imageLabel}${index + 1}`,
        file: row.file || dataUrlToFile(row.preview, row.fileName || `reference-${index + 1}.png`),
      }));
      const data = await generateRender({ lineArt, references: referenceFiles, baseUrl: config.baseUrl, apiKey: config.apiKey, model: config.model, prompt, size, count: config.count });
      setResults(data.images || []);
      showMessage(`${T.generatedPrefix} ${data.images?.length || 0} ${T.generatedSuffix}`, "success");
    } catch (error: unknown) {
      const err = error as { userMessage?: string; response?: { data?: { detail?: string } }; message?: string };
      showMessage(err.userMessage || err.response?.data?.detail || err.message || T.failed, "error");
    } finally {
      setLoading(false);
    }
  }

  function downloadActive() {
    if (!activeResult) return;
    const link = document.createElement("a");
    link.href = activeResult.src;
    link.download = `${T.filenamePrefix}-${activeIndex + 1}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function resetAll() {
    revokePreview(lineArtPreview);
    references.forEach((row) => revokePreview(row.preview));
    setLineArt(null);
    setLineArtPreview("");
    setReferences(defaultReferenceRows());
    setPrompt(T.defaultPrompt);
    setSize("1k");
    setResults([]);
    setActiveIndex(0);
    showMessage(T.resetKeptConfig, "");
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
          <h1 className="text-[18px] font-semibold text-[#1C1C1E]">{T.title}</h1>
          <p className="text-[12px] text-[#8E8E93] mt-1">{T.subtitle}</p>
        </div>
        {message && <span className={`text-[12px] px-3 py-1 rounded-full font-medium ${statusClass}`}>{message}</span>}
      </div>

      <Collapsible title={T.configTitle} open={settingsOpen} onToggle={() => setSettingsOpen((open) => !open)}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <TextField label="Base URL" value={config.baseUrl} onChange={(value) => updateConfig("baseUrl", value)} placeholder="https://api.example.com/v1" />
          <TextField label="API Key" type="password" value={config.apiKey} onChange={(value) => updateConfig("apiKey", value)} placeholder="sk-..." />
          <TextField label="Model" value={config.model} onChange={(value) => updateConfig("model", value)} placeholder="image-edit-model" />
          <label className="block">
            <span className="text-[12px] font-medium text-[#8E8E93]">Count</span>
            <input type="number" min={1} max={4} value={config.count} onChange={(event) => updateConfig("count", clampCount(event.target.value))} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" />
          </label>
        </div>
      </Collapsible>

      <Collapsible title={T.libraryTitle} open={libraryOpen} onToggle={() => setLibraryOpen((open) => !open)}>
        <LibraryManager
          library={library}
          uploadLabel={libraryUploadLabel}
          onUploadLabel={setLibraryUploadLabel}
          onUpload={uploadLibraryFiles}
          onRemove={removeLibraryItem}
        />
      </Collapsible>

      <UploadPanel title={T.lineArtTitle} kicker="Line Art" preview={lineArtPreview} fileName={lineArt?.name} onPick={pickLineArt} onClear={() => { revokePreview(lineArtPreview); setLineArt(null); setLineArtPreview(""); }} />

      <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold text-[#007AFF] uppercase">Reference</p>
            <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{T.referencesTitle}</h2>
          </div>
          <button type="button" onClick={addReference} className="px-3 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 transition-colors">+ {T.addReference}</button>
        </div>
        <datalist id="render-part-options">{PART_OPTIONS.map((option) => <option key={option} value={option} />)}</datalist>
        <div className="space-y-3">
          {references.map((row, index) => (
            <ReferenceEditor
              key={row.id}
              row={row}
              index={index}
              library={library}
              onLabel={(value) => updateReference(row.id, { label: value })}
              onPick={(event) => pickReference(row.id, event)}
              onClear={() => clearReference(row.id)}
              onRemove={() => removeReference(row.id)}
              onSave={() => saveReferenceToLibrary(row)}
              onChooseLibrary={(itemId) => applyLibraryItem(row.id, itemId)}
            />
          ))}
        </div>
      </section>

      <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_160px] gap-3">
          <label className="block"><span className="text-[12px] font-medium text-[#8E8E93]">Prompt</span><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none resize-y" /></label>
          <label className="block"><span className="text-[12px] font-medium text-[#8E8E93]">Size</span><select value={size} onChange={(event) => setSize(event.target.value)} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none bg-white"><option value="1k">1K</option><option value="2k">2K</option><option value="4k">4K</option></select></label>
        </div>
        <div className="flex gap-2 justify-end">
          <button type="button" onClick={resetAll} disabled={loading} className="px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/70 disabled:opacity-50 transition-colors">{T.clear}</button>
          <button type="button" onClick={handleGenerate} disabled={!canGenerate || loading} className="px-5 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 disabled:opacity-50 transition-colors">{loading ? T.generatingShort : T.generate}</button>
        </div>
      </section>

      <ResultPanel activeResult={activeResult} activeIndex={activeIndex} results={results} loading={loading} onDownload={downloadActive} onSelect={setActiveIndex} />
    </div>
  );
}

function Collapsible({ title, open, onToggle, children }: { title: string; open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 overflow-hidden"><button type="button" onClick={onToggle} className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-[#F2F2F7] transition-colors"><span className="text-[14px] font-semibold text-[#1C1C1E]">{title}</span><span className="text-[12px] text-[#8E8E93]">{open ? T.collapse : T.expand}</span></button>{open && <div className="px-5 pb-5 border-t border-[#E5E5EA]/60 pt-4">{children}</div>}</section>;
}

function TextField({ label, value, onChange, placeholder, type = "text" }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; type?: string }) {
  return <label className="block"><span className="text-[12px] font-medium text-[#8E8E93]">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none" /></label>;
}

function UploadPanel({ title, kicker, preview, fileName, onPick, onClear }: { title: string; kicker: string; preview: string; fileName?: string; onPick: (event: ChangeEvent<HTMLInputElement>) => void; onClear: () => void }) {
  return <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4 min-h-[320px] flex flex-col"><div className="flex items-center justify-between mb-3"><div><p className="text-[11px] font-semibold text-[#007AFF] uppercase">{kicker}</p><h2 className="text-[15px] font-semibold text-[#1C1C1E]">{title}</h2></div><button type="button" onClick={onClear} className="w-8 h-8 rounded-lg text-[#8E8E93] hover:text-[#1C1C1E] hover:bg-[#F2F2F7] transition-colors" aria-label={`${T.clearPrefix}${title}`}>x</button></div><label className="flex-1 min-h-[240px] rounded-xl border border-dashed border-[#C7C7CC] bg-[#F2F2F7] hover:bg-[#E5E5EA]/50 transition-colors cursor-pointer overflow-hidden flex items-center justify-center"><input type="file" accept="image/*" onChange={onPick} className="hidden" />{preview ? <img src={preview} alt={`${title}${T.preview}`} className="w-full h-full object-contain" /> : <span className="text-center text-[13px] text-[#8E8E93]">{T.clickUpload}{title}<br /><span className="text-[12px]">{T.support}</span></span>}</label>{fileName && <p className="text-[12px] text-[#8E8E93] mt-2 truncate">{fileName}</p>}</section>;
}

function ReferenceEditor({ row, index, library, onLabel, onPick, onClear, onRemove, onSave, onChooseLibrary }: { row: ReferenceRow; index: number; library: LibraryItem[]; onLabel: (value: string) => void; onPick: (event: ChangeEvent<HTMLInputElement>) => void; onClear: () => void; onRemove: () => void; onSave: () => void; onChooseLibrary: (itemId: string) => void }) {
  const matchedLibrary = library.filter((item) => !row.label.trim() || item.label === row.label.trim());
  const choices = matchedLibrary.length ? matchedLibrary : library;
  return <div className="grid grid-cols-1 lg:grid-cols-[180px_1fr_190px] gap-3 rounded-xl border border-[#E5E5EA]/60 bg-[#FAFAFC] p-3"><label className="block"><span className="text-[12px] font-medium text-[#8E8E93]">{T.partLabel} {index + 1}</span><input list="render-part-options" value={row.label} onChange={(event) => onLabel(event.target.value)} placeholder={T.customPart} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none bg-white" /></label><label className="min-h-[120px] rounded-xl border border-dashed border-[#C7C7CC] bg-white hover:bg-[#F2F2F7] transition-colors cursor-pointer overflow-hidden flex items-center justify-center"><input type="file" accept="image/*" onChange={onPick} className="hidden" />{row.preview ? <img src={row.preview} alt={`${row.label || T.imageLabel}${T.preview}`} className="max-h-[160px] max-w-full object-contain" /> : <span className="text-center text-[13px] text-[#8E8E93]">{T.clickUpload}{T.imageLabel}<br /><span className="text-[12px]">{T.support}</span></span>}</label><div className="flex flex-col gap-2"><select value="" onChange={(event) => { if (event.target.value) onChooseLibrary(event.target.value); }} className="px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg bg-white focus:border-[#007AFF] focus:outline-none"><option value="">{T.chooseFromLibrary}</option>{choices.map((item) => <option key={item.id} value={item.id}>{item.label} - {item.name}</option>)}</select>{row.fileName && <p className="text-[12px] text-[#8E8E93] truncate">{row.fileName}</p>}<button type="button" onClick={onSave} disabled={!row.preview} className="px-3 py-2 text-[12px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/70 disabled:opacity-50 transition-colors">{T.saveToLibrary}</button><div className="grid grid-cols-2 gap-2"><button type="button" onClick={onClear} className="px-3 py-2 text-[12px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/70 transition-colors">{T.clear}</button><button type="button" onClick={onRemove} className="px-3 py-2 text-[12px] font-medium rounded-lg bg-[#FF3B30]/10 text-[#FF3B30] hover:bg-[#FF3B30]/15 transition-colors">{T.remove}</button></div></div></div>;
}

function LibraryManager({ library, uploadLabel, onUploadLabel, onUpload, onRemove }: { library: LibraryItem[]; uploadLabel: string; onUploadLabel: (value: string) => void; onUpload: (event: ChangeEvent<HTMLInputElement>) => void; onRemove: (itemId: string) => void }) {
  const groups = PART_OPTIONS.map((label) => ({
    label,
    items: library.filter((item) => item.label === label),
  }));
  const customGroups = Array.from(new Set(library.map((item) => item.label).filter((label) => !PART_OPTIONS.includes(label)))).map((label) => ({
    label,
    items: library.filter((item) => item.label === label),
  }));
  const allGroups = [...groups, ...customGroups].filter((group) => group.items.length);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-3 rounded-xl border border-[#E5E5EA]/60 bg-[#FAFAFC] p-3">
        <label className="block">
          <span className="text-[12px] font-medium text-[#8E8E93]">{T.libraryCategory}</span>
          <input list="render-part-options" value={uploadLabel} onChange={(event) => onUploadLabel(event.target.value)} className="w-full mt-1 px-3 py-2 text-[13px] border border-[#E5E5EA]/60 rounded-lg focus:border-[#007AFF] focus:outline-none bg-white" />
        </label>
        <label className="min-h-[86px] rounded-xl border border-dashed border-[#C7C7CC] bg-white hover:bg-[#F2F2F7] transition-colors cursor-pointer flex items-center justify-center">
          <input type="file" accept="image/*" multiple onChange={onUpload} className="hidden" />
          <span className="text-center text-[13px] text-[#8E8E93]">{T.uploadToLibrary}<br /><span className="text-[12px]">{T.batchUploadLibrary}</span></span>
        </label>
      </div>
      {allGroups.length ? (
        <div className="space-y-4">
          {allGroups.map((group) => (
            <div key={group.label} className="space-y-2">
              <h3 className="text-[13px] font-semibold text-[#1C1C1E]">{group.label}</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {group.items.map((item) => <LibraryCard key={item.id} item={item} onRemove={() => onRemove(item.id)} />)}
              </div>
            </div>
          ))}
        </div>
      ) : <p className="text-[13px] text-[#8E8E93]">{T.noLibrary}</p>}
    </div>
  );
}

function LibraryCard({ item, onRemove }: { item: LibraryItem; onRemove: () => void }) {
  return <div className="rounded-xl border border-[#E5E5EA]/60 bg-[#FAFAFC] p-3"><div className="aspect-[4/3] rounded-lg bg-white border border-[#E5E5EA]/60 overflow-hidden flex items-center justify-center"><img src={item.dataUrl} alt={item.name} className="w-full h-full object-contain" /></div><div className="mt-2 flex items-start justify-between gap-2"><div className="min-w-0"><p className="text-[12px] font-semibold text-[#1C1C1E] truncate">{item.label}</p><p className="text-[12px] text-[#8E8E93] truncate">{item.name}</p></div><button type="button" onClick={onRemove} className="text-[12px] text-[#FF3B30] shrink-0">{T.remove}</button></div></div>;
}

function ResultPanel({ activeResult, activeIndex, results, loading, onDownload, onSelect }: { activeResult: RenderImageResult | null; activeIndex: number; results: RenderImageResult[]; loading: boolean; onDownload: () => void; onSelect: (index: number) => void }) {
  return <section className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4 min-h-[320px] flex flex-col"><div className="flex items-center justify-between mb-3"><div><p className="text-[11px] font-semibold text-[#007AFF] uppercase">Result</p><h2 className="text-[15px] font-semibold text-[#1C1C1E]">{T.resultTitle}</h2></div><button type="button" onClick={onDownload} disabled={!activeResult} className="px-3 py-1.5 text-[12px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] disabled:opacity-50 hover:bg-[#E5E5EA]/70 transition-colors">{T.download}</button></div><div className="flex-1 min-h-[240px] rounded-xl bg-[#F2F2F7] border border-[#E5E5EA]/60 flex items-center justify-center overflow-hidden">{loading ? <div className="text-center text-[#8E8E93] text-[13px]"><div className="w-8 h-8 mx-auto mb-3 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />{T.generatingShort}</div> : activeResult ? <img src={activeResult.src} alt={`${T.resultAlt} ${activeIndex + 1}`} className="max-w-full max-h-[520px] object-contain" /> : <p className="text-[13px] text-[#8E8E93]">{T.emptyResult}</p>}</div>{results.length > 1 && <div className="flex gap-2 mt-3 overflow-x-auto">{results.map((image, index) => <button key={`${image.src.slice(0, 32)}-${index}`} type="button" onClick={() => onSelect(index)} className={`w-16 h-16 rounded-lg border overflow-hidden shrink-0 ${index === activeIndex ? "border-[#007AFF]" : "border-[#E5E5EA]"}`}><img src={image.src} alt={`${T.resultThumb} ${index + 1}`} className="w-full h-full object-cover" /></button>)}</div>}</section>;
}

function defaultReferenceRows(): ReferenceRow[] {
  return DEFAULT_REFERENCE_LABELS.map(newReferenceRow);
}

function newReferenceRow(label: string): ReferenceRow {
  return { id: createId(), label, file: null, preview: "", fileName: "" };
}

function createId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

function clampCount(value: unknown): number {
  const parsed = Number.parseInt(String(value ?? 1), 10);
  if (Number.isNaN(parsed)) return 1;
  return Math.min(Math.max(parsed, 1), 4);
}

function revokePreview(value: string) {
  if (value.startsWith("blob:")) URL.revokeObjectURL(value);
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function dataUrlToFile(dataUrl: string, fileName: string): File {
  const [header, data] = dataUrl.split(",");
  const mime = header.match(/data:(.*?);base64/)?.[1] || "image/png";
  const binary = atob(data || "");
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return new File([bytes], fileName, { type: mime });
}
