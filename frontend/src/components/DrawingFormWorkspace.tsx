"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode, type PointerEvent, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, ChevronUp, GripHorizontal, RefreshCw } from "lucide-react";
import type { DoorFormData } from "@/lib/types";
import { apiErrorMessage, generateCadPreview } from "@/lib/api";
import { LatestPreviewQueue, previewFingerprint, previewReadiness } from "@/lib/liveCadPreview";
import CadPreviewPanel from "./CadPreviewPanel";
import { clampFloatingPosition, initialFloatingPosition, type FloatingPosition } from "@/lib/floatingPreview";

export default function DrawingFormWorkspace({ data, children }: { data: DoorFormData; children: ReactNode }) {
  const [automatic, setAutomatic] = useState(false);
  const [svg, setSvg] = useState<string | null>(null);
  const [renderedKey, setRenderedKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [position, setPosition] = useState<FloatingPosition | null>(null);
  const panelRef = useRef<HTMLElement>(null);
  const dragRef = useRef<{ pointerId: number; clientX: number; clientY: number; origin: FloatingPosition } | null>(null);
  const moveFrame = useRef<number | null>(null);
  const pendingPosition = useRef<FloatingPosition | null>(null);
  const queue = useRef<LatestPreviewQueue<DoorFormData> | null>(null);
  const latest = useRef(data);
  const key = useMemo(() => previewFingerprint(data), [data]);
  const readiness = previewReadiness(data);
  useEffect(() => {
    const worker = new LatestPreviewQueue(generateCadPreview, {
      success: (value, fingerprint) => { setSvg(value); setRenderedKey(fingerprint); setError(""); },
      error: value => setError(apiErrorMessage(value, "预览更新失败，请重试")),
      busy: setBusy,
    });
    queue.current = worker;
    return () => { worker.dispose(); queue.current = null; };
  }, []);
  useEffect(() => { latest.current = data; }, [data]);
  useEffect(() => {
    const worker = queue.current;
    if (!worker) return;
    worker.setDesired(key);
    worker.cancelPending();
    if (!automatic || readiness || collapsed) return;
    const timer = window.setTimeout(() => worker.enqueue(key, latest.current), 1500);
    return () => window.clearTimeout(timer);
  }, [key, automatic, readiness, collapsed]);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setPosition(initialFloatingPosition({ width: innerWidth, height: innerHeight })));
    return () => { cancelAnimationFrame(frame); if (moveFrame.current !== null) cancelAnimationFrame(moveFrame.current); };
  }, []);
  const positioned = position !== null;
  useEffect(() => {
    if (!positioned || !panelRef.current) return;
    const panel = panelRef.current;
    const constrain = () => {
      const rect = panel.getBoundingClientRect();
      setPosition(value => {
        if (!value) return value;
        const next = clampFloatingPosition(value, rect, { width: innerWidth, height: innerHeight });
        return next.x === value.x && next.y === value.y ? value : next;
      });
    };
    const observer = new ResizeObserver(constrain);
    observer.observe(panel);
    window.addEventListener("resize", constrain);
    return () => { observer.disconnect(); window.removeEventListener("resize", constrain); };
  }, [positioned]);
  const constrainPosition = (value: FloatingPosition) => {
    const rect = panelRef.current?.getBoundingClientRect();
    return rect ? clampFloatingPosition(value, rect, { width: innerWidth, height: innerHeight }) : value;
  };
  const startDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary || event.button !== 0 || !position) return;
    event.preventDefault();
    dragRef.current = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, origin: position };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveDrag = (event: PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    pendingPosition.current = constrainPosition({ x: drag.origin.x + event.clientX - drag.clientX, y: drag.origin.y + event.clientY - drag.clientY });
    if (moveFrame.current === null) moveFrame.current = requestAnimationFrame(() => {
      moveFrame.current = null;
      if (pendingPosition.current) setPosition(pendingPosition.current);
      pendingPosition.current = null;
    });
  };
  const endDrag = () => {
    dragRef.current = null;
    if (moveFrame.current !== null) { cancelAnimationFrame(moveFrame.current); moveFrame.current = null; }
    if (pendingPosition.current) setPosition(pendingPosition.current);
    pendingPosition.current = null;
  };
  const moveWithKeys = (event: KeyboardEvent<HTMLDivElement>) => {
    const direction = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
    if (!direction || !position) return;
    event.preventDefault();
    const step = event.shiftKey ? 50 : 10;
    setPosition(constrainPosition({ x: position.x + direction[0] * step, y: position.y + direction[1] * step }));
  };
  const refresh = () => {
    if (readiness) return;
    queue.current?.setDesired(key);
    queue.current?.enqueue(key, data);
  };
  return (
    <div className="drawing-form-workspace">
      <div className="min-w-0">{children}</div>
      {position && createPortal(<aside ref={panelRef} data-live-cad-preview data-minimized={collapsed} aria-label="图纸悬浮预览"
        className="drawing-preview-dock" style={{ left: position.x, top: position.y }}>
        <div className="flex items-center justify-between gap-2">
          <div role="button" tabIndex={0} aria-label="移动图纸小窗" title="拖动小窗" data-preview-drag-handle
            onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag} onLostPointerCapture={endDrag}
            onKeyDown={moveWithKeys} className="flex min-h-9 min-w-0 flex-1 cursor-grab touch-none select-none items-center gap-2 text-[#636366] active:cursor-grabbing">
            <GripHorizontal size={16} aria-hidden="true" /><h4 className="whitespace-nowrap text-sm font-semibold text-[#242429]">图纸小窗</h4>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-[#62626B]">
            自动预览
            <input type="checkbox" role="switch" aria-label="自动预览" checked={automatic}
              onChange={event => setAutomatic(event.target.checked)} className="h-4 w-4 accent-[#007AFF]" />
          </label>
          <button type="button" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? "展开小窗" : "收起小窗"}
            title={collapsed ? "展开小窗" : "收起小窗"} aria-expanded={!collapsed}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#636366] hover:bg-[#F2F2F7]">
            {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
        </div>
        {!collapsed && <>
        <div className="my-3 flex items-center justify-between gap-2">
          <span role="status" className="text-xs text-[#777780]">{busy ? "正在更新..." : readiness || (svg && renderedKey !== key ? "参数已修改，待刷新" : automatic ? "自动预览已开启" : "自动预览已关闭")}</span>
          <button type="button" onClick={refresh} disabled={busy || Boolean(readiness)} title="刷新小窗" aria-label="刷新小窗"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[#D1D5DB] text-[#636366] hover:text-[#007AFF] disabled:opacity-40"><RefreshCw size={15} className={busy ? "animate-spin" : ""} /></button>
        </div>
        {error && <p role="alert" className="mb-3 text-xs text-[#C93531]">{error}</p>}
        {svg ? <CadPreviewPanel svg={svg} loading={false} embedded />
          : <div className="flex min-h-44 items-center justify-center rounded-md border border-[#E2E2E8] bg-[#F8FAFC] text-xs text-[#777780]">{busy ? "正在生成预览..." : "暂无预览"}</div>}
        </>}
      </aside>, document.body)}
    </div>
  );
}
