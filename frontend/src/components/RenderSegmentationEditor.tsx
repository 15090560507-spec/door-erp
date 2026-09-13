"use client";

import { useEffect, useRef, useState } from "react";
import { Brush, Check, Eraser, MousePointer2, X } from "lucide-react";
import type { RenderReferenceRole, RenderSegmentation } from "@/lib/renderApi";

const ROLES: Array<{ role: RenderReferenceRole; label: string; color: string }> = [
  { role: "panel", label: "门扇", color: "#FF9500" },
  { role: "trim", label: "门套/门头门柱", color: "#34C759" },
  { role: "frame", label: "门框", color: "#007AFF" },
  { role: "glass", label: "玻璃", color: "#5AC8FA" },
  { role: "hardware", label: "五金", color: "#AF52DE" },
];

type EditTool = "assign" | "add" | "erase";

export default function RenderSegmentationEditor({
  segmentation,
  onCancel,
  onConfirm,
}: {
  segmentation: RenderSegmentation;
  onCancel: () => void;
  onConfirm: (masks: Partial<Record<RenderReferenceRole, Blob>>) => Promise<void>;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const sourceRef = useRef<HTMLImageElement | null>(null);
  const masksRef = useRef<Partial<Record<RenderReferenceRole, HTMLCanvasElement>>>({});
  const drawingRef = useRef(false);
  const [activeRole, setActiveRole] = useState<RenderReferenceRole>("panel");
  const [tool, setTool] = useState<EditTool>("assign");
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [opacity, setOpacity] = useState(42);

  useEffect(() => {
    let cancelled = false;
    const source = new Image();
    source.onload = async () => {
      if (cancelled) return;
      sourceRef.current = source;
      const canvas = canvasRef.current;
      if (!canvas) return;
      canvas.width = source.naturalWidth;
      canvas.height = source.naturalHeight;
      const nextMasks: Partial<Record<RenderReferenceRole, HTMLCanvasElement>> = {};
      await Promise.all(ROLES.map(async ({ role }) => {
        const maskCanvas = document.createElement("canvas");
        maskCanvas.width = source.naturalWidth;
        maskCanvas.height = source.naturalHeight;
        const context = maskCanvas.getContext("2d", { willReadFrequently: true });
        if (!context) return;
        context.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
        const url = segmentation.masks?.[role]?.url;
        if (url) {
          const image = await loadImage(url);
          context.drawImage(image, 0, 0, maskCanvas.width, maskCanvas.height);
          const pixels = context.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
          for (let index = 0; index < pixels.data.length; index += 4) {
            const value = pixels.data[index];
            pixels.data[index] = 255;
            pixels.data[index + 1] = 255;
            pixels.data[index + 2] = 255;
            pixels.data[index + 3] = value;
          }
          context.putImageData(pixels, 0, 0);
        }
        nextMasks[role] = maskCanvas;
      }));
      if (cancelled) return;
      masksRef.current = nextMasks;
      setReady(true);
    };
    source.src = segmentation.source.url;
    return () => { cancelled = true; };
  }, [segmentation]);

  useEffect(() => {
    if (!ready) return;
    renderCanvas(canvasRef.current, sourceRef.current, masksRef.current, opacity / 100);
  }, [opacity, ready]);

  function paint(event: React.PointerEvent<HTMLCanvasElement>, start = false) {
    const canvas = canvasRef.current;
    if (!canvas || !ready || (!drawingRef.current && !start)) return;
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) * canvas.width / rect.width;
    const y = (event.clientY - rect.top) * canvas.height / rect.height;
    const radius = Math.max(8, Math.min(canvas.width, canvas.height) * (tool === "assign" ? 0.018 : 0.032));
    if (tool !== "erase") {
      for (const { role } of ROLES) {
        if (role === activeRole) continue;
        drawMaskPoint(masksRef.current[role], x, y, radius, false);
      }
      drawMaskPoint(masksRef.current[activeRole], x, y, radius, true);
    } else {
      drawMaskPoint(masksRef.current[activeRole], x, y, radius, false);
    }
    renderCanvas(canvas, sourceRef.current, masksRef.current, opacity / 100);
  }

  async function confirm() {
    setSaving(true);
    try {
      const entries = await Promise.all(ROLES.map(async ({ role }) => [role, await canvasBlob(masksRef.current[role])] as const));
      const masks = Object.fromEntries(entries.filter((entry): entry is [RenderReferenceRole, Blob] => Boolean(entry[1]))) as Partial<Record<RenderReferenceRole, Blob>>;
      await onConfirm(masks);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/45 p-4 backdrop-blur-[2px]">
      <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-white/60 bg-[#F7F7FA] shadow-2xl">
        <div className="flex items-start gap-4 border-b border-[#E5E5EA] bg-white px-5 py-4">
          <div className="min-w-0 flex-1">
            <h2 className="text-[16px] font-semibold text-[#1C1C1E]">确认部件区域</h2>
            <p className="mt-1 text-[12px] text-[#8E8E93]">彩色区域决定参考图的作用范围。确认边界后，精准生成会严格沿用这些区域。</p>
          </div>
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${segmentation.confidence >= 0.75 ? "bg-[#34C759]/12 text-[#248A3D]" : "bg-[#FF9500]/12 text-[#9A5A00]"}`}>
            识别置信度 {Math.round(segmentation.confidence * 100)}%
          </span>
          <button type="button" onClick={onCancel} className="grid h-8 w-8 place-items-center rounded-lg text-[#636366] hover:bg-[#F2F2F7]" title="关闭"><X size={17} /></button>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[220px_1fr]">
          <aside className="space-y-4 overflow-y-auto border-r border-[#E5E5EA] bg-white p-4">
            <div>
              <p className="mb-2 text-[12px] font-semibold text-[#1C1C1E]">当前归类</p>
              <div className="space-y-1.5">
                {ROLES.map((item) => (
                  <button key={item.role} type="button" onClick={() => setActiveRole(item.role)} className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-[12px] ${activeRole === item.role ? "border-[#1C1C1E] bg-[#F2F2F7] font-semibold" : "border-transparent hover:bg-[#F7F7FA]"}`}>
                    <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: item.color }} />{item.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-2 text-[12px] font-semibold text-[#1C1C1E]">修正工具</p>
              <div className="grid grid-cols-3 gap-1.5">
                <ToolButton active={tool === "assign"} label="点选" icon={<MousePointer2 size={15} />} onClick={() => setTool("assign")} />
                <ToolButton active={tool === "add"} label="补充" icon={<Brush size={15} />} onClick={() => setTool("add")} />
                <ToolButton active={tool === "erase"} label="擦除" icon={<Eraser size={15} />} onClick={() => setTool("erase")} />
              </div>
            </div>
            <label className="block">
              <span className="mb-2 block text-[12px] font-semibold text-[#1C1C1E]">蒙版透明度</span>
              <input type="range" min={15} max={75} value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} className="w-full accent-[#007AFF]" />
            </label>
            {segmentation.warnings?.map((warning) => <p key={warning} className="rounded-lg bg-[#FF9500]/10 px-3 py-2 text-[11px] leading-5 text-[#9A5A00]">{warning}</p>)}
          </aside>

          <div className="min-h-0 overflow-auto p-4">
            <div className="flex min-h-[420px] items-center justify-center rounded-xl border border-[#D1D1D6] bg-[#ECECF1] p-3">
              {!ready && <span className="text-[13px] text-[#8E8E93]">正在加载区域...</span>}
              <canvas
                ref={canvasRef}
                onPointerDown={(event) => { drawingRef.current = true; event.currentTarget.setPointerCapture(event.pointerId); paint(event, true); }}
                onPointerMove={(event) => paint(event)}
                onPointerUp={() => { drawingRef.current = false; }}
                onPointerCancel={() => { drawingRef.current = false; }}
                className={`max-h-[64vh] max-w-full touch-none bg-white shadow-sm ${ready ? "block" : "hidden"}`}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[#E5E5EA] bg-white px-5 py-3">
          <button type="button" onClick={onCancel} className="rounded-lg border border-[#D1D1D6] bg-white px-4 py-2 text-[13px] font-medium text-[#3C3C43]">取消</button>
          <button type="button" onClick={() => void confirm()} disabled={!ready || saving} className="inline-flex items-center gap-2 rounded-lg bg-[#007AFF] px-4 py-2 text-[13px] font-medium text-white disabled:opacity-50"><Check size={15} />{saving ? "保存中..." : "确认区域"}</button>
        </div>
      </div>
    </div>
  );
}

function ToolButton({ active, label, icon, onClick }: { active: boolean; label: string; icon: React.ReactNode; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-2 text-[11px] ${active ? "border-[#007AFF] bg-[#007AFF]/8 text-[#007AFF]" : "border-[#E5E5EA] text-[#636366]"}`}>{icon}{label}</button>;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("区域蒙版加载失败"));
    image.src = url;
  });
}

function drawMaskPoint(canvas: HTMLCanvasElement | undefined, x: number, y: number, radius: number, enabled: boolean) {
  const context = canvas?.getContext("2d");
  if (!context) return;
  context.globalCompositeOperation = enabled ? "source-over" : "destination-out";
  context.fillStyle = "white";
  context.beginPath();
  context.arc(x, y, radius, 0, Math.PI * 2);
  context.fill();
  context.globalCompositeOperation = "source-over";
}

function renderCanvas(
  canvas: HTMLCanvasElement | null,
  source: HTMLImageElement | null,
  masks: Partial<Record<RenderReferenceRole, HTMLCanvasElement>>,
  opacity: number,
) {
  const context = canvas?.getContext("2d");
  if (!canvas || !context || !source) return;
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  for (const item of ROLES) {
    const mask = masks[item.role];
    if (!mask) continue;
    const colorCanvas = document.createElement("canvas");
    colorCanvas.width = canvas.width;
    colorCanvas.height = canvas.height;
    const colorContext = colorCanvas.getContext("2d");
    if (!colorContext) continue;
    colorContext.fillStyle = item.color;
    colorContext.fillRect(0, 0, canvas.width, canvas.height);
    colorContext.globalCompositeOperation = "destination-in";
    colorContext.drawImage(mask, 0, 0);
    context.save();
    context.globalAlpha = opacity;
    context.drawImage(colorCanvas, 0, 0);
    context.restore();
  }
}

function canvasBlob(canvas: HTMLCanvasElement | undefined): Promise<Blob | null> {
  return new Promise((resolve) => canvas ? canvas.toBlob(resolve, "image/png") : resolve(null));
}
