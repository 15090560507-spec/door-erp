"use client";
import { Plus, Trash2 } from "lucide-react";
import type { PatternDefinition } from "@/lib/referencePatternTypes";

export default function PatternLineEditor({ definition, onChange }: { definition: PatternDefinition; onChange: (value: PatternDefinition) => void }) {
  const add = (vertical: boolean) => onChange({ ...definition, paths: [...definition.paths, { points: vertical ? [[0.5, 0.1], [0.5, 0.9]] : [[0.1, 0.5], [0.9, 0.5]], closed: false }] });
  return <details className="mt-3 border-t border-[#E5E5EA] pt-3"><summary className="cursor-pointer text-sm font-medium">线条校正（{definition.paths.length}组）</summary>
    <div className="my-3 flex flex-wrap gap-2"><button type="button" disabled={definition.paths.length >= 128} className="ui-button ui-button--secondary" onClick={() => add(false)}><Plus size={14} />添加横线</button><button type="button" disabled={definition.paths.length >= 128} className="ui-button ui-button--secondary" onClick={() => add(true)}><Plus size={14} />添加竖线</button></div>
    <div className="max-h-64 space-y-2 overflow-auto">{definition.paths.map((path, index) => <div key={index} className="border border-[#E5E5EA] p-2">
      <div className="mb-2 flex items-center gap-2 text-xs"><strong className="mr-auto">第{index + 1}组 · {path.closed ? "闭合" : "开放"}</strong><button type="button" title="删除线条组" aria-label={`删除第${index + 1}组线条`} disabled={definition.paths.length <= 1} className="ui-button ui-button--quiet" onClick={() => onChange({ ...definition, paths: definition.paths.filter((_, i) => i !== index) })}><Trash2 size={14} /></button></div>
      <div className="grid gap-2 sm:grid-cols-2">{path.points.map((point, pointIndex) => <div key={pointIndex} className="flex min-w-0 items-center gap-1 text-xs"><span className="shrink-0">点{pointIndex + 1}</span>{([0, 1] as const).map(axis => <label key={axis} className="flex min-w-0 items-center gap-1">{axis === 0 ? "X%" : "Y%"}<input aria-label={`第${index + 1}组点${pointIndex + 1}${axis === 0 ? "X" : "Y"}百分比`} type="number" min="0" max="100" step="0.1" value={Number((point[axis] * 100).toFixed(3))} className="h-8 w-full min-w-0 border border-[#C7C7CC] px-1" onChange={event => {
        const paths = definition.paths.map((item, i) => i !== index ? item : { ...item, points: item.points.map((value, j) => j !== pointIndex ? value : value.map((coordinate, k) => k === axis ? Number(event.target.value) / 100 : coordinate) as [number, number]) });
        onChange({ ...definition, paths });
      }} /></label>)}</div>)}</div>
    </div>)}</div>
  </details>;
}
