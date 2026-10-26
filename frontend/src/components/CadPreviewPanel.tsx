"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Maximize2, Minus, Plus, RotateCcw, X } from "lucide-react";

type Side = "both" | "front" | "back";
const sides: { value: Side; label: string }[] = [
  { value: "front", label: "正面" }, { value: "back", label: "反面" }, { value: "both", label: "正面和反面" },
];

function PreviewCanvas({ svg, side, fitFrame = false }: { svg: string; side: Side; fitFrame?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  // Keep unrelated parent renders from replacing the fitted SVG DOM.
  const markup = useMemo(() => ({ __html: svg }), [svg]);
  useLayoutEffect(() => {
    const root = ref.current?.querySelector("svg");
    if (!root) return;
    const groups = [...root.querySelectorAll<SVGGElement>("g[data-cad-view]")];
    const fit = () => {
      const boxes: DOMRect[] = [];
      for (const group of groups) {
        const visible = side === "both" || group.dataset.cadView === side;
        group.style.display = visible ? "" : "none";
        if (visible) boxes.push(group.getBBox());
      }
      const valid = boxes.filter(box => box.width > 0 && box.height > 0);
      if (valid.length) {
        const left = Math.min(...valid.map(box => box.x)), top = Math.min(...valid.map(box => box.y));
        const right = Math.max(...valid.map(box => box.x + box.width)), bottom = Math.max(...valid.map(box => box.y + box.height));
        const pad = Math.max(right - left, bottom - top) * 0.02;
        root.setAttribute("viewBox", `${left - pad} ${top - pad} ${right - left + pad * 2} ${bottom - top + pad * 2}`);
        if (fitFrame && ref.current) ref.current.style.aspectRatio = String((right - left + pad * 2) / (bottom - top + pad * 2));
      }
      root.setAttribute("preserveAspectRatio", "xMidYMid meet");
    };
    fit();
    let active = true;
    const observer = new ResizeObserver(fit);
    if (ref.current) observer.observe(ref.current);
    void document.fonts.ready.then(() => { if (active) fit(); });
    return () => { active = false; observer.disconnect(); };
  }, [svg, side, fitFrame]);
  return <div ref={ref} data-cad-preview-canvas
    style={fitFrame ? { aspectRatio: "16/10" } : undefined}
    className={`${fitFrame ? "max-h-[min(65vh,640px)]" : "h-full"} w-full [&_svg]:block [&_svg]:h-full [&_svg]:w-full`}
    dangerouslySetInnerHTML={markup} />;
}

export default function CadPreviewPanel({ svg, loading }: { svg: string | null; loading: boolean }) {
  const [side, setSide] = useState<Side>("both");
  const [isOpen, setIsOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setIsOpen(false); setZoom(1); }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);
  if (!svg && !loading) return null;
  const controls = (
    <div role="group" aria-label="预览视图" className="inline-flex max-w-full rounded-md border border-[#D1D5DB] bg-white p-0.5">
      {sides.map(item => <button key={item.value} type="button" aria-pressed={side === item.value}
        disabled={!svg || loading || (item.value === "back" && !svg.includes('data-cad-view="back"'))}
        onClick={() => setSide(item.value)}
        className={`min-h-9 px-3 py-1.5 text-sm rounded ${side === item.value ? "bg-[#E8F1FF] font-semibold text-[#007AFF]" : "text-[#636366] hover:bg-[#F2F2F7]"} disabled:opacity-40`}>{item.label}</button>)}
    </div>
  );
  return (
    <section data-cad-preview-panel className="rounded-lg border border-black/5 bg-white p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h4 className="text-[17px] font-semibold text-[#1C1C1E]">CAD 图纸预览</h4>
        <div className="flex flex-wrap items-center gap-2">{controls}
          <button type="button" onClick={() => setIsOpen(true)} disabled={!svg || loading} title="放大查看" aria-label="放大查看"
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-[#D1D5DB] text-[#636366] hover:text-[#007AFF] disabled:opacity-40"><Maximize2 size={17} /></button>
        </div>
      </div>
      <div className="w-full overflow-hidden rounded-md border border-[#D1D5DB] bg-[#F8FAFC]">
        {loading ? <div role="status" className="flex aspect-[16/10] max-h-[65vh] items-center justify-center text-sm text-[#636366]">正在生成预览...</div>
          : svg && <PreviewCanvas svg={svg} side={side} fitFrame />}
      </div>
      {isOpen && svg && createPortal(
        <div className="fixed inset-0 z-[200] bg-black/70 p-3 sm:p-4">
          <div role="dialog" aria-modal="true" aria-label="CAD 图纸预览" className="flex h-full flex-col overflow-hidden rounded-lg bg-white">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E5EA] p-3">
              {controls}
              <div className="flex items-center gap-2">
                <button type="button" title="缩小" aria-label="缩小" onClick={() => setZoom(value => Math.max(1, value - 0.25))} className="ui-button ui-button--secondary !h-9 !w-9 !p-0"><Minus size={16} /></button>
                <button type="button" title="适应画布" aria-label="适应画布" onClick={() => setZoom(1)} className="ui-button ui-button--secondary !h-9 !w-9 !p-0"><RotateCcw size={16} /></button>
                <span className="w-12 text-center text-xs tabular-nums">{Math.round(zoom * 100)}%</span>
                <button type="button" title="放大" aria-label="放大" onClick={() => setZoom(value => Math.min(4, value + 0.25))} className="ui-button ui-button--secondary !h-9 !w-9 !p-0"><Plus size={16} /></button>
                <button type="button" title="关闭" aria-label="关闭" onClick={() => { setIsOpen(false); setZoom(1); }} className="ui-button ui-button--secondary !h-9 !w-9 !p-0"><X size={16} /></button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto bg-[#F8FAFC]">
              <div style={{ width: `${zoom * 100}%`, height: `${zoom * 100}%` }}><PreviewCanvas svg={svg} side={side} /></div>
            </div>
          </div>
        </div>, document.body
      )}
    </section>
  );
}
