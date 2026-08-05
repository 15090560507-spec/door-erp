"use client";

import { PointerEvent, useMemo, useRef, useState } from "react";
import type { LineArtCropBox, LineArtExtraction } from "@/lib/renderApi";

interface Props {
  extraction: LineArtExtraction;
  onCancel: () => void;
  onSave: (value: { front: LineArtCropBox; back: LineArtCropBox; rotation: number }) => Promise<void>;
}

type Side = "front" | "back";

export default function LineArtCropEditor({ extraction, onCancel, onSave }: Props) {
  const imageRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [front, setFront] = useState<LineArtCropBox>(extraction.front.crop || fallbackBox(extraction, 0));
  const [back, setBack] = useState<LineArtCropBox>(extraction.back.crop || fallbackBox(extraction, 1));
  const [rotation, setRotation] = useState(0);
  const [saving, setSaving] = useState(false);
  const dimensions = useMemo(() => rotatedDimensions(extraction.sourceWidth || 1, extraction.sourceHeight || 1, rotation), [extraction.sourceHeight, extraction.sourceWidth, rotation]);

  function startDrag(event: PointerEvent<HTMLElement>, side: Side, resize: boolean) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const startX = event.clientX;
    const startY = event.clientY;
    const original = side === "front" ? front : back;
    const scaleX = dimensions.width / canvas.clientWidth;
    const scaleY = dimensions.height / canvas.clientHeight;
    const setBox = side === "front" ? setFront : setBack;

    function move(moveEvent: globalThis.PointerEvent) {
      const dx = (moveEvent.clientX - startX) * scaleX;
      const dy = (moveEvent.clientY - startY) * scaleY;
      if (resize) {
        setBox(clampBox({ ...original, width: original.width + dx, height: original.height + dy }, dimensions));
      } else {
        setBox(clampBox({ ...original, x: original.x + dx, y: original.y + dy }, dimensions));
      }
    }
    function finish() {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
    }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish, { once: true });
  }

  async function save() {
    setSaving(true);
    try {
      await onSave({ front: roundBox(front), back: roundBox(back), rotation });
    } finally {
      setSaving(false);
    }
  }

  function changeRotation(nextRotation: number) {
    const delta = (nextRotation - rotation + 360) % 360;
    if (!delta) return;
    setFront(rotateBox(front, dimensions, delta));
    setBack(rotateBox(back, dimensions, delta));
    setRotation(nextRotation);
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/65 p-4" onClick={onCancel}>
      <div className="max-h-[94vh] w-full max-w-6xl overflow-auto rounded-xl bg-white p-4 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div>
            <h2 className="text-[16px] font-semibold text-[#1C1C1E]">调整正反面裁剪</h2>
            <p className="mt-1 text-[12px] text-[#8E8E93]">拖动框移动，拖动右下角调整大小。蓝色为正面，绿色为反面。</p>
          </div>
          <div className="flex-1" />
          {[0, 90, 180, 270].map((value) => (
            <button key={value} type="button" onClick={() => changeRotation(value)} className={`rounded-lg px-3 py-2 text-[12px] ${rotation === value ? "bg-[#007AFF] text-white" : "bg-[#F2F2F7]"}`}>{value}°</button>
          ))}
          <button type="button" onClick={onCancel} className="rounded-lg bg-[#F2F2F7] px-3 py-2 text-[12px]">取消</button>
          <button type="button" onClick={() => void save()} disabled={saving} className="rounded-lg bg-[#007AFF] px-4 py-2 text-[12px] font-medium text-white disabled:opacity-50">{saving ? "处理中..." : "保存裁剪"}</button>
        </div>
        <div className="flex justify-center overflow-auto rounded-xl bg-[#F2F2F7] p-3">
          <div
            ref={canvasRef}
            className="relative w-full max-w-full overflow-hidden"
            style={{
              aspectRatio: `${dimensions.width} / ${dimensions.height}`,
              width: `min(100%, calc(76vh * ${dimensions.width} / ${dimensions.height}))`,
            }}
          >
            <img
              ref={imageRef}
              src={extraction.sourceUrl}
              alt="订单原图"
              draggable={false}
              className="absolute left-1/2 top-1/2 select-none object-fill"
              style={{
                width: rotation % 180 === 0 ? "100%" : `${dimensions.height / dimensions.width * 100}%`,
                height: rotation % 180 === 0 ? "100%" : `${dimensions.width / dimensions.height * 100}%`,
                transform: `translate(-50%, -50%) rotate(${rotation}deg)`,
              }}
            />
            <CropOverlay side="front" box={front} dimensions={dimensions} onPointerDown={startDrag} />
            <CropOverlay side="back" box={back} dimensions={dimensions} onPointerDown={startDrag} />
          </div>
        </div>
      </div>
    </div>
  );
}

function CropOverlay({ side, box, dimensions, onPointerDown }: { side: Side; box: LineArtCropBox; dimensions: { width: number; height: number }; onPointerDown: (event: PointerEvent<HTMLElement>, side: Side, resize: boolean) => void }) {
  const color = side === "front" ? "#007AFF" : "#34C759";
  return (
    <div
      onPointerDown={(event) => onPointerDown(event, side, false)}
      className="absolute cursor-move border-2"
      style={{ left: `${box.x / dimensions.width * 100}%`, top: `${box.y / dimensions.height * 100}%`, width: `${box.width / dimensions.width * 100}%`, height: `${box.height / dimensions.height * 100}%`, borderColor: color }}
    >
      <span className="absolute left-0 top-0 px-1 py-0.5 text-[11px] font-medium text-white" style={{ backgroundColor: color }}>{side === "front" ? "正面" : "反面"}</span>
      <span onPointerDown={(event) => { event.stopPropagation(); onPointerDown(event, side, true); }} className="absolute -bottom-1.5 -right-1.5 h-4 w-4 cursor-se-resize rounded-full border-2 border-white" style={{ backgroundColor: color }} />
    </div>
  );
}

function fallbackBox(extraction: LineArtExtraction, index: number): LineArtCropBox {
  const width = extraction.sourceWidth || 1;
  const height = extraction.sourceHeight || 1;
  return { x: Math.round(width * (index ? 0.52 : 0.04)), y: Math.round(height * 0.18), width: Math.round(width * 0.44), height: Math.round(height * 0.76) };
}

function rotatedDimensions(width: number, height: number, rotation: number) {
  return rotation % 180 === 0 ? { width, height } : { width: height, height: width };
}

function clampBox(box: LineArtCropBox, dimensions: { width: number; height: number }): LineArtCropBox {
  const width = Math.max(20, Math.min(box.width, dimensions.width));
  const height = Math.max(20, Math.min(box.height, dimensions.height));
  const x = Math.max(0, Math.min(box.x, dimensions.width - width));
  const y = Math.max(0, Math.min(box.y, dimensions.height - height));
  return { x, y, width, height };
}

function roundBox(box: LineArtCropBox): LineArtCropBox {
  return { x: Math.round(box.x), y: Math.round(box.y), width: Math.round(box.width), height: Math.round(box.height) };
}

function rotateBox(box: LineArtCropBox, dimensions: { width: number; height: number }, degrees: number): LineArtCropBox {
  let result = { ...box };
  let width = dimensions.width;
  let height = dimensions.height;
  const turns = Math.round(degrees / 90) % 4;
  for (let index = 0; index < turns; index += 1) {
    result = {
      x: height - result.y - result.height,
      y: result.x,
      width: result.height,
      height: result.width,
    };
    [width, height] = [height, width];
  }
  return clampBox(result, { width, height });
}
