"use client";
import { ImagePlus, Trash2 } from "lucide-react";
import { useState } from "react";
import type { DoorFormData } from "@/lib/types";
import { REFERENCE_STYLE, type PatternSlot } from "@/lib/referencePatternTypes";
import ReferencePatternDialog from "./ReferencePatternDialog";

export default function ReferencePatternField({ data, onChange, slot, styleKey, title, readOnly }: {
  data: DoorFormData; onChange: (value: DoorFormData) => void; slot: PatternSlot; styleKey: keyof DoorFormData; title: string; readOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const snapshot = data.reference_patterns?.[slot], pendingJob = data.reference_pattern_jobs?.[slot];
  return <div className="space-y-2">
    <div className="flex flex-wrap items-center gap-2"><button type="button" disabled={readOnly} onClick={() => setOpen(true)} className="ui-button ui-button--secondary"><ImagePlus size={15} />{pendingJob ? "查看参考图识别" : "参考图识别"}</button>
      {snapshot && <><span className="min-w-0 break-words text-xs text-[#636366]">{data[styleKey] === REFERENCE_STYLE ? "已应用" : "未启用"} · {snapshot.band_width}mm</span><button type="button" title="移除参考线稿" aria-label={`移除${title}参考线稿`} disabled={readOnly} className="ui-button ui-button--quiet" onClick={() => { const patterns = { ...data.reference_patterns }, jobs = { ...data.reference_pattern_jobs }; delete patterns[slot]; delete jobs[slot]; onChange({ ...data, reference_patterns: patterns, reference_pattern_jobs: jobs, ...(data[styleKey] === REFERENCE_STYLE ? { [styleKey]: "无线条" } : {}) }); }}><Trash2 size={14} /></button></>}
    </div>
    {open && <ReferencePatternDialog title={title} transom={slot === "transom"} snapshot={snapshot} pendingJob={pendingJob}
      onClose={() => setOpen(false)} onPending={id => onChange({ ...data, reference_pattern_jobs: { ...data.reference_pattern_jobs, [slot]: id } })}
      onApply={value => { const jobs = { ...data.reference_pattern_jobs }; delete jobs[slot]; onChange({ ...data, [styleKey]: REFERENCE_STYLE, reference_patterns: { ...data.reference_patterns, [slot]: value }, reference_pattern_jobs: jobs }); setOpen(false); }} />}
  </div>;
}
