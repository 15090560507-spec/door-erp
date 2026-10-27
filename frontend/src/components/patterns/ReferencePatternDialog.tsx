"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { LoaderCircle, ScanLine, Save } from "lucide-react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import PatternImageInput, { croppedImage, FULL_CROP, type CropRect } from "./PatternImageInput";
import PatternLineEditor from "./PatternLineEditor";
import { getPatternConnection, getPatternJob, getPatternSource, listPatternTemplates, previewPattern, recognizePattern, savePatternTemplate } from "@/lib/referencePatternApi";
import { placementOf, type AppliedPattern, type PatternDefinition, type PatternJob, type PatternPlacement, type PatternPreview, type PatternTemplate } from "@/lib/referencePatternTypes";

type Props = { title: string; transom?: boolean; snapshot?: AppliedPattern; pendingJob?: string; onPending: (id: string) => void; onApply: (snapshot: AppliedPattern) => void; onClose: () => void };
export default function ReferencePatternDialog({ title, transom, snapshot, pendingJob, onPending, onApply, onClose }: Props) {
  const [connection, setConnection] = useState<{ configured: boolean; model: string } | null>(null);
  const [templates, setTemplates] = useState<PatternTemplate[]>([]);
  const [definition, setDefinition] = useState<PatternDefinition | null>(pendingJob ? null : snapshot?.definition || null);
  const [settings, setSettings] = useState(() => snapshot ? placementOf(snapshot) : { band_width: 20, inset: 20, detail_x: 80, detail_y: 80, mirror: false, source_job_id: "" });
  const [width, setWidth] = useState(transom ? 1400 : 500), [height, setHeight] = useState(transom ? 400 : 1400);
  const [preview, setPreview] = useState<PatternPreview | null>(null), [previewError, setPreviewError] = useState("");
  const [previewing, setPreviewing] = useState(false), [source, setSource] = useState("");
  const sourceRef = useRef(""), imageRef = useRef<HTMLImageElement>(null), sourceEpoch = useRef(0);
  const [file, setFile] = useState<File | null>(null), [crop, setCrop] = useState<CropRect>(FULL_CROP);
  const [jobId, setJobId] = useState(pendingJob || snapshot?.source_job_id || ""), [job, setJob] = useState<PatternJob | null>(null);
  const [submitting, setSubmitting] = useState(false), [saving, setSaving] = useState(false), [error, setError] = useState("");
  const [pollVersion, setPollVersion] = useState(0);
  const [reviewed, setReviewed] = useState(false), [templateName, setTemplateName] = useState(snapshot?.definition.name || "");
  const requestRef = useRef<{ file: File; key: string } | null>(null);
  const busy = submitting || job?.status === "queued" || job?.status === "running";
  const placement = useMemo<PatternPlacement | null>(() => definition ? { ...settings, definition } : null, [definition, settings]);
  const replaceSource = (blob: Blob) => {
    if (sourceRef.current) URL.revokeObjectURL(sourceRef.current);
    const url = URL.createObjectURL(blob); sourceRef.current = url; setSource(url);
  };
  useEffect(() => () => { if (sourceRef.current) URL.revokeObjectURL(sourceRef.current); }, []);
  useEffect(() => {
    let active = true;
    void getPatternConnection().then(conn => { if (active) setConnection(conn); }).catch(error => { if (active) setError(message(error)); });
    void listPatternTemplates().then(items => { if (active) setTemplates(items); }).catch(error => { if (active) setError(message(error)); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!jobId) return;
    let active = true, timer: ReturnType<typeof setTimeout>;
    const epoch = ++sourceEpoch.current;
    const poll = async () => {
      try {
        const next = await getPatternJob(jobId);
        if (!active) return;
        setJob(next);
        if (next.status === "completed" && next.definition) {
          if (pendingJob || !snapshot) { setDefinition(next.definition); setTemplateName(next.definition.name); setReviewed(false); setPreview(null); }
          setSettings(current => ({ ...current, source_job_id: next.id }));
        } else if (next.status === "failed") setError(next.error);
        else timer = setTimeout(() => void poll(), 1500);
      } catch (error) { if (active) setError(message(error)); }
    };
    void poll();
    void getPatternSource(jobId).then(blob => { if (active && epoch === sourceEpoch.current) replaceSource(blob); }).catch(error => { if (active) setError(message(error)); });
    return () => { active = false; clearTimeout(timer); };
  }, [jobId, pendingJob, snapshot, pollVersion]);
  useEffect(() => {
    if (!placement) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setPreviewing(true); setPreview(null); setPreviewError("");
      void previewPattern(placement, width, height, controller.signal).then(value => { if (!controller.signal.aborted) setPreview(value); })
        .catch(error => { if (!controller.signal.aborted) setPreviewError(message(error)); })
        .finally(() => { if (!controller.signal.aborted) setPreviewing(false); });
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [placement, width, height]);
  const acceptFile = (next: File) => {
    if (busy) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(next.type) || next.size > 8 * 1024 * 1024) { setError("请选择8MB以内的JPG、PNG或WebP图片"); return; }
    sourceEpoch.current++; setJobId(""); setJob(null); setFile(next); replaceSource(next); setCrop(FULL_CROP);
    setDefinition(null); setPreview(null); setError(""); setReviewed(false); requestRef.current = null;
  };
  const start = async () => {
    if (!imageRef.current || busy || !connection?.configured) return;
    setSubmitting(true); setError("");
    try {
      const cropped = file ? await croppedImage(imageRef.current, crop) : new File([await getPatternSource(jobId || settings.source_job_id)], "reference.jpg", { type: "image/jpeg" });
      if (!requestRef.current) requestRef.current = { file: cropped, key: crypto.randomUUID() };
      const result = await recognizePattern(requestRef.current.file, requestRef.current.key);
      setFile(null); setCrop(FULL_CROP); setJob(result); setJobId(result.id); onPending(result.id);
      setDefinition(null); setPreview(null); setReviewed(false);
    } catch (error) { setError(message(error)); }
    finally { setSubmitting(false); }
  };
  const ready = Boolean(placement && preview && !previewError && !previewing && !busy && reviewed && !saving && !file);
  const apply = async (save: boolean) => {
    if (!ready || !placement) return;
    const applied: AppliedPattern = { ...placement, reviewed: true };
    if (save && !templateName.trim()) { setError("请填写模板名称"); return; }
    setSaving(true); setError("");
    try { if (save) await savePatternTemplate(templateName.trim(), applied); onApply(applied); }
    catch (error) { setError(message(error)); }
    finally { setSaving(false); }
  };
  const changeNumber = (key: "band_width" | "inset" | "detail_x" | "detail_y", value: number) => { setReviewed(false); setPreview(null); setSettings(current => ({ ...current, [key]: value })); };
  const chooseTemplate = (id: string) => {
    const selected = templates.find(item => item.id === id); if (!selected) return;
    const epoch = ++sourceEpoch.current;
    requestRef.current = null;
    setJobId(""); setJob(null); setFile(null); setDefinition(selected.snapshot.definition); setSettings(placementOf(selected.snapshot));
    setTemplateName(selected.name); setReviewed(false); setPreview(null); setError("");
    if (selected.snapshot.source_job_id) void getPatternSource(selected.snapshot.source_job_id).then(blob => { if (epoch === sourceEpoch.current) replaceSource(blob); }).catch(error => setError(message(error)));
    else { if (sourceRef.current) URL.revokeObjectURL(sourceRef.current); sourceRef.current = ""; setSource(""); }
  };
  const previewPath = preview?.loops.map(loop => loop.map(([x, y], index) => `${index ? "L" : "M"}${x},${y}`).join(" ") + " Z").join(" ");
  return <ViewportDialog open title={`${title} · 参考图识别`} size="wide" closeOnBackdrop={false} onClose={() => { if (!submitting && !saving) onClose(); }}
    footer={<><label className="mr-auto flex w-full items-center gap-2 text-sm sm:w-auto"><input type="checkbox" disabled={!preview || Boolean(busy) || Boolean(file) || saving} checked={reviewed} onChange={event => setReviewed(event.target.checked)} />我已核对线条和连接关系</label>
      <button type="button" className="ui-button ui-button--secondary" disabled={!ready} onClick={() => void apply(true)}><Save size={15} />应用并保存模板</button>
      <button type="button" className="ui-button ui-button--primary" disabled={!ready} onClick={() => void apply(false)}>仅应用到本樘门</button></>}>
    <div className="mb-4 flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] pb-3 text-sm"><span className="mr-auto min-w-0 break-all">报价共用模型：<strong>{connection?.model || "未配置"}</strong></span>
      <select aria-label="选择已有款式模板" className="h-9 min-w-0 max-w-full border border-[#C7C7CC] px-2" value="" disabled={busy} onChange={event => chooseTemplate(event.target.value)}><option value="">选择已有款式模板</option>{templates.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
    </div>
    {!connection?.configured && connection && <p className="mb-3 text-sm text-[#B26A00]">尚未配置视觉模型，请先在报价系统配置AI连接。</p>}
    {error && <p role="alert" className="mb-3 break-words text-sm text-red-700">{error}</p>}
    {jobId && error && job?.status !== "failed" && <button type="button" className="ui-button ui-button--secondary mb-3" onClick={() => { setError(""); setPollVersion(value => value + 1); }}>重新查询结果</button>}
    <div className="grid min-w-0 gap-4 md:grid-cols-2">
      <PatternImageInput source={source} crop={crop} canCrop={Boolean(file)} disabled={Boolean(busy)} imageRef={imageRef} onFile={acceptFile} onCrop={value => { setCrop(value); requestRef.current = null; }} />
      <section className="min-w-0 border border-[#D7D7DE] p-3"><h3 className="mb-3 text-sm font-semibold">线稿试配预览</h3>
        <div className="flex h-[400px] items-center justify-center bg-[#F6F7F9]">
          {preview && !file ? <svg aria-label="识别线稿预览" viewBox={`0 0 ${preview.width} ${preview.height}`} className="h-full w-full p-3"><g transform={`translate(0 ${preview.height}) scale(1 -1)`}><rect width={preview.width} height={preview.height} fill="white" stroke="#007AFF" strokeWidth="2" /><path d={previewPath} fill="#343B41" fillRule="evenodd" /></g></svg>
            : <span role="status" className="p-4 text-center text-sm text-[#636366]">{busy ? "正在识别，可关闭后从本栏查看结果" : previewing ? "计算线稿中…" : previewError || "暂无线稿"}</span>}
        </div>
        {previewError && <p role="alert" className="mt-2 text-sm text-red-700">{previewError}</p>}
      </section>
    </div>
    <div className="my-3 flex flex-wrap items-center gap-3"><button type="button" className="ui-button ui-button--primary" disabled={Boolean(busy) || !source || !connection?.configured} onClick={() => { if (job?.status === "failed" || job?.status === "completed") requestRef.current = null; void start(); }}>{busy ? <LoaderCircle className="animate-spin" size={15} /> : <ScanLine size={15} />}{busy ? "识别中…" : job ? "重新识别线稿" : "识别线稿"}</button><span className="text-xs text-[#8E8E93]">识别会调用模型并计费，重新识别可能再次计费。</span></div>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <NumberField label="线宽(mm)" value={settings.band_width} list="reference-band-widths" onChange={value => changeNumber("band_width", value)} />
      <NumberField label="外边距(mm)" value={settings.inset} onChange={value => changeNumber("inset", value)} />
      <NumberField label="左右固定造型区(mm)" value={settings.detail_x} onChange={value => changeNumber("detail_x", value)} />
      <NumberField label="上下固定造型区(mm)" value={settings.detail_y} onChange={value => changeNumber("detail_y", value)} />
      <NumberField label="试配宽(mm)" value={width} onChange={value => { setReviewed(false); setPreview(null); setWidth(value); }} />
      <NumberField label="试配高(mm)" value={height} onChange={value => { setReviewed(false); setPreview(null); setHeight(value); }} />
    </div>
    <datalist id="reference-band-widths"><option value="15" /><option value="20" /></datalist>
    <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={settings.mirror} onChange={event => { setReviewed(false); setPreview(null); setSettings(current => ({ ...current, mirror: event.target.checked })); }} />左右镜像</label>
    {definition?.warnings.map((warning, index) => <p key={index} className="mt-2 break-words text-sm text-[#B26A00]">待核对：{warning}</p>)}
    {definition && <PatternLineEditor definition={definition} onChange={value => { setDefinition(value); setReviewed(false); setPreview(null); }} />}
    {definition && <><p className="mt-3 text-xs text-[#B26A00]">自动识别可能漏线或误连，请核对后应用；不确定的尺寸不能直接作为加工依据。</p>
      <label className="mt-3 block text-sm">模板名称（另存时填写）<input value={templateName} onChange={event => setTemplateName(event.target.value)} maxLength={80} className="mt-1 h-9 w-full border border-[#C7C7CC] px-3" /></label></>}
  </ViewportDialog>;
}

function NumberField({ label, value, list, onChange }: { label: string; value: number; list?: string; onChange: (value: number) => void }) { return <label className="text-xs text-[#636366]">{label}<input type="number" min="0" step="any" list={list} value={value} onChange={event => onChange(Number(event.target.value))} className="mt-1 h-9 w-full border border-[#C7C7CC] px-3 text-sm text-[#1C1C1E]" /></label>; }
function message(error: unknown) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as Error)?.message || "参考图处理失败"; }
