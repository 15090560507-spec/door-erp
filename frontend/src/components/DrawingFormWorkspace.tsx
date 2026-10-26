"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode, type PointerEvent, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, ChevronUp, GripHorizontal, Maximize2, Minus, Plus, RefreshCw } from "lucide-react";
import type { DoorFormData } from "@/lib/types";
import { apiErrorMessage, generateCadPreview } from "@/lib/api";
import { LatestPreviewQueue, previewFingerprint, previewReadiness } from "@/lib/liveCadPreview";
import CadPreviewPanel, { type CadPreviewSide } from "./CadPreviewPanel";
import { clampFloatingPosition, clampFloatingSize, DEFAULT_FLOATING_SIZE, initialFloatingPosition, shouldDockPreview, type FloatingPosition, type FloatingSize } from "@/lib/floatingPreview";

type Props = {
  data: DoorFormData; children: ReactNode; actions: ReactNode;
  svg: string | null; renderedKey: string; manualLoading: boolean;
  onPreview: (svg: string, fingerprint: string) => void;
};
type Motion = { pointerId: number; clientX: number; clientY: number; origin: FloatingPosition; size: FloatingSize; resize: boolean };

export default function DrawingFormWorkspace({ data, children, actions, svg, renderedKey, manualLoading, onPreview }: Props) {
  const [automatic, setAutomatic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [position, setPosition] = useState<FloatingPosition | null>(null);
  const [size, setSize] = useState(DEFAULT_FLOATING_SIZE);
  const [docked, setDocked] = useState(false);
  const [home, setHome] = useState<HTMLDivElement | null>(null);
  const [side, setSide] = useState<CadPreviewSide>("front");
  const panelRef = useRef<HTMLElement>(null);
  const actionRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<Motion | null>(null);
  const moveFrame = useRef<number | null>(null);
  const pending = useRef<{ position: FloatingPosition; size?: FloatingSize } | null>(null);
  const sizeRef = useRef(size);
  const queue = useRef<LatestPreviewQueue<DoorFormData> | null>(null);
  const latest = useRef(data);
  const key = useMemo(() => previewFingerprint(data), [data]);
  const readiness = previewReadiness(data);
  const minimized = collapsed && !docked;
  const generating = busy || manualLoading;

  useEffect(() => {
    const worker = new LatestPreviewQueue(generateCadPreview, {
      success: (value, fingerprint) => { onPreview(value, fingerprint); setError(""); },
      error: value => setError(apiErrorMessage(value, "预览更新失败，请重试")),
      busy: setBusy,
    });
    queue.current = worker;
    return () => { worker.dispose(); queue.current = null; };
  }, [onPreview]);
  useEffect(() => { latest.current = data; }, [data]);
  useEffect(() => { sizeRef.current = size; }, [size]);
  useEffect(() => {
    const worker = queue.current;
    if (!worker) return;
    worker.setDesired(key);
    worker.cancelPending();
    if (!automatic || readiness || minimized) return;
    const timer = window.setTimeout(() => worker.enqueue(key, latest.current), 1500);
    return () => window.clearTimeout(timer);
  }, [key, automatic, readiness, minimized]);
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const viewport = { width: innerWidth, height: innerHeight };
      setSize(clampFloatingSize(DEFAULT_FLOATING_SIZE, viewport));
      setPosition(initialFloatingPosition(viewport));
    });
    const resize = () => {
      const viewport = { width: innerWidth, height: innerHeight };
      const next = clampFloatingSize(sizeRef.current, viewport);
      setSize(value => value.width === next.width && value.height === next.height ? value : next);
      setPosition(value => value && clampFloatingPosition(value, next, viewport));
    };
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      if (moveFrame.current !== null) cancelAnimationFrame(moveFrame.current);
    };
  }, []);
  useEffect(() => {
    let frame: number | null = null;
    const measure = () => {
      frame = null;
      if (actionRef.current) setDocked(shouldDockPreview(actionRef.current.getBoundingClientRect().bottom, innerHeight));
    };
    const schedule = () => { if (frame === null) frame = requestAnimationFrame(measure); };
    const observer = new ResizeObserver(schedule);
    if (actionRef.current) observer.observe(actionRef.current);
    window.addEventListener("scroll", schedule, true);
    window.addEventListener("resize", schedule);
    schedule();
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", schedule, true);
      window.removeEventListener("resize", schedule);
      if (frame !== null) cancelAnimationFrame(frame);
    };
  }, []);
  const positioned = position !== null;
  useEffect(() => {
    if (!positioned || docked || !panelRef.current) return;
    const observer = new ResizeObserver(() => {
      const rect = panelRef.current?.getBoundingClientRect();
      if (!rect) return;
      setPosition(value => {
        if (!value) return value;
        const next = clampFloatingPosition(value, rect, { width: innerWidth, height: innerHeight });
        return next.x === value.x && next.y === value.y ? value : next;
      });
    });
    observer.observe(panelRef.current);
    return () => observer.disconnect();
  }, [positioned, docked]);
  const endMotion = () => {
    dragRef.current = null;
    if (moveFrame.current !== null) { cancelAnimationFrame(moveFrame.current); moveFrame.current = null; }
    if (pending.current) {
      setPosition(pending.current.position);
      if (pending.current.size) setSize(pending.current.size);
    }
    pending.current = null;
  };
  const startMotion = (event: PointerEvent<HTMLElement>, resize = false) => {
    if (!event.isPrimary || event.button !== 0 || !position || docked) return;
    event.preventDefault();
    dragRef.current = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, origin: position, size, resize };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveMotion = (event: PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.clientX, dy = event.clientY - drag.clientY;
    const viewport = { width: innerWidth, height: innerHeight };
    const nextSize = drag.resize ? clampFloatingSize({ width: drag.size.width + dx, height: drag.size.height + dy }, viewport) : undefined;
    const rect = nextSize ?? panelRef.current?.getBoundingClientRect() ?? drag.size;
    pending.current = {
      position: clampFloatingPosition(drag.resize ? drag.origin : { x: drag.origin.x + dx, y: drag.origin.y + dy }, rect, viewport),
      size: nextSize,
    };
    if (moveFrame.current === null) moveFrame.current = requestAnimationFrame(() => {
      moveFrame.current = null;
      if (pending.current) {
        setPosition(pending.current.position);
        if (pending.current.size) setSize(pending.current.size);
      }
      pending.current = null;
    });
  };
  const moveWithKeys = (event: KeyboardEvent<HTMLDivElement>) => {
    const direction = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
    if (!direction || !position || docked) return;
    event.preventDefault();
    const step = event.shiftKey ? 50 : 10;
    setPosition(clampFloatingPosition({ x: position.x + direction[0] * step, y: position.y + direction[1] * step },
      panelRef.current?.getBoundingClientRect() ?? size, { width: innerWidth, height: innerHeight }));
  };
  const scaleWindow = (factor: number) => {
    const viewport = { width: innerWidth, height: innerHeight };
    const next = clampFloatingSize({ width: size.width * factor, height: size.height * factor }, viewport);
    setSize(next);
    setPosition(value => value && clampFloatingPosition(value, next, viewport));
  };
  const refresh = () => {
    if (readiness) return;
    queue.current?.setDesired(key);
    queue.current?.enqueue(key, data);
  };
  const target = docked ? home : typeof document === "undefined" ? null : document.body;
  const floatingStyle = position ? {
    left: position.x, top: position.y, width: size.width, height: minimized ? undefined : size.height,
  } : undefined;
  return (
    <div className="drawing-form-workspace">
      <div className="min-w-0">{children}</div>
      <div ref={actionRef} data-preview-action-boundary className="mt-6">{actions}</div>
      <div ref={setHome} data-preview-home className={docked ? "mt-4" : ""} />
      {position && target && createPortal(
        <aside ref={panelRef} data-live-cad-preview data-preview-mode={docked ? "docked" : "floating"} data-minimized={minimized}
          aria-label={docked ? "CAD 图纸预览" : "图纸悬浮预览"}
          className={docked ? "drawing-preview-home-panel" : "drawing-preview-dock"} style={docked ? undefined : floatingStyle}>
          <div className="flex shrink-0 items-center justify-between gap-2">
            {docked ? <h4 className="text-base font-semibold text-[#242429]">CAD 图纸预览</h4> :
              <div role="button" tabIndex={0} aria-label="移动图纸小窗" title="拖动小窗" data-preview-drag-handle
                onPointerDown={event => startMotion(event)} onPointerMove={moveMotion} onPointerUp={endMotion} onPointerCancel={endMotion} onLostPointerCapture={endMotion}
                onKeyDown={moveWithKeys} className="flex min-h-9 min-w-0 flex-1 cursor-grab touch-none select-none items-center gap-2 text-[#636366] active:cursor-grabbing">
                <GripHorizontal size={16} aria-hidden="true" /><h4 className="whitespace-nowrap text-sm font-semibold text-[#242429]">图纸小窗</h4>
              </div>}
            <label className="flex cursor-pointer items-center gap-2 text-xs text-[#62626B]">
              自动预览<input type="checkbox" role="switch" aria-label="自动预览" checked={automatic}
                onChange={event => setAutomatic(event.target.checked)} className="h-4 w-4 accent-[#007AFF]" />
            </label>
            {!docked && <button type="button" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? "展开小窗" : "收起小窗"}
              title={collapsed ? "展开小窗" : "收起小窗"} aria-expanded={!collapsed}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#636366] hover:bg-[#F2F2F7]">
              {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
            </button>}
          </div>
          {!minimized && <div className="drawing-preview-body">
            <div className="my-3 flex items-center justify-between gap-2">
              <span role="status" className="text-xs text-[#777780]">{generating ? "正在更新..." : readiness || (svg && renderedKey !== key ? "参数已修改，待刷新" : automatic ? "自动预览已开启" : "自动预览已关闭")}</span>
              <div className="flex shrink-0 items-center gap-1">
                {!docked && <>
                  <button type="button" onClick={() => scaleWindow(1 / 1.1)} aria-label="缩小小窗" title="缩小小窗" className="ui-button ui-button--secondary !h-8 !w-8 !p-0"><Minus size={15} /></button>
                  <button type="button" onClick={() => scaleWindow(1.1)} aria-label="放大小窗" title="放大小窗" className="ui-button ui-button--secondary !h-8 !w-8 !p-0"><Plus size={15} /></button>
                </>}
                <button type="button" onClick={refresh} disabled={generating || Boolean(readiness)} title="刷新小窗" aria-label="刷新小窗"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#D1D5DB] text-[#636366] hover:text-[#007AFF] disabled:opacity-40"><RefreshCw size={15} className={generating ? "animate-spin" : ""} /></button>
              </div>
            </div>
            {error && <p role="alert" className="mb-3 text-xs text-[#C93531]">{error}</p>}
            {svg ? <CadPreviewPanel svg={svg} loading={false} embedded side={side} onSideChange={setSide} />
              : <div className={docked ? "drawing-preview-empty drawing-preview-empty--large" : "drawing-preview-empty"}>{generating ? "正在生成预览..." : "暂无预览"}</div>}
          </div>}
          {!docked && !minimized && <button type="button" aria-label="调整小窗大小" title="拖动调整小窗大小"
            onPointerDown={event => startMotion(event, true)} onPointerMove={moveMotion} onPointerUp={endMotion} onPointerCancel={endMotion} onLostPointerCapture={endMotion}
            className="absolute bottom-0 right-0 flex h-6 w-6 cursor-nwse-resize touch-none items-center justify-center text-[#777780]"><Maximize2 size={12} aria-hidden="true" /></button>}
        </aside>, target)}
    </div>
  );
}
