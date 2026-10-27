"use client";
/* eslint-disable @next/next/no-img-element */
import { RotateCcw, Upload } from "lucide-react";
import { useRef } from "react";

export type CropRect = { x: number; y: number; width: number; height: number };
export const FULL_CROP: CropRect = { x: 0, y: 0, width: 1, height: 1 };

export async function croppedImage(image: HTMLImageElement, crop: CropRect): Promise<File> {
  const sourceWidth = image.naturalWidth * crop.width, sourceHeight = image.naturalHeight * crop.height;
  if (sourceWidth < 16 || sourceHeight < 16) throw new Error("裁剪区域过小，请保留完整图案");
  const canvas = document.createElement("canvas"), scale = Math.min(1, 1600 / Math.max(sourceWidth, sourceHeight));
  canvas.width = Math.max(1, Math.round(sourceWidth * scale)); canvas.height = Math.max(1, Math.round(sourceHeight * scale));
  const context = canvas.getContext("2d")!;
  context.fillStyle = "white"; context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, image.naturalWidth * crop.x, image.naturalHeight * crop.y, sourceWidth, sourceHeight, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error("图片处理失败")), "image/jpeg", 0.9));
  return new File([blob], "reference-crop.jpg", { type: "image/jpeg" });
}

export default function PatternImageInput({ source, crop, disabled, canCrop, imageRef, onCrop, onFile }: {
  source: string; crop: CropRect; disabled: boolean; canCrop: boolean; imageRef: React.RefObject<HTMLImageElement | null>;
  onCrop: (crop: CropRect) => void; onFile: (file: File) => void;
}) {
  const input = useRef<HTMLInputElement>(null), drag = useRef<{ x: number; y: number } | null>(null);
  const position = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) };
  };
  return <div className="min-w-0 border border-[#D7D7DE] p-3" tabIndex={0} aria-label="B2或气窗参考图上传区"
    onPaste={event => { if (disabled) return; const file = Array.from(event.clipboardData.files).find(file => file.type.startsWith("image/")); if (file) { event.preventDefault(); onFile(file); } }}
    onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); if (!disabled && event.dataTransfer.files[0]) onFile(event.dataTransfer.files[0]); }}>
    <div className="mb-3 flex items-center gap-2"><h3 className="mr-auto text-sm font-semibold">参考原图</h3>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" aria-label="选择参考图" disabled={disabled} onChange={event => { const file = event.target.files?.[0]; if (file) onFile(file); event.target.value = ""; }} />
      <button type="button" disabled={disabled} className="ui-button ui-button--secondary" onClick={() => input.current?.click()}><Upload size={15} />上传图片</button>
      <button type="button" title="重置裁剪" aria-label="重置裁剪" disabled={disabled || !canCrop} className="ui-button ui-button--quiet" onClick={() => onCrop(FULL_CROP)}><RotateCcw size={16} /></button>
    </div>
    <div className="flex min-h-72 items-center justify-center overflow-hidden bg-[#F6F7F9]">
      {source ? <div className={`relative max-w-full touch-none ${canCrop ? "cursor-crosshair" : ""}`}
        onPointerDown={event => { if (!canCrop || disabled || event.button !== 0) return; event.preventDefault(); drag.current = position(event); event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerMove={event => { if (!drag.current) return; const point = position(event), start = drag.current; onCrop({ x: Math.min(start.x, point.x), y: Math.min(start.y, point.y), width: Math.max(0.01, Math.abs(start.x - point.x)), height: Math.max(0.01, Math.abs(start.y - point.y)) }); }}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
        <img ref={imageRef} src={source} alt="待识别参考图" draggable={false} className="block max-h-[400px] max-w-full" />
        {canCrop && <div className="pointer-events-none absolute border-2 border-[#007AFF] bg-[#007AFF]/10" style={{ left: `${crop.x * 100}%`, top: `${crop.y * 100}%`, width: `${crop.width * 100}%`, height: `${crop.height * 100}%` }} />}
      </div> : <span className="text-sm text-[#636366]">上传 / Ctrl+V 粘贴 / 拖入图片</span>}
    </div>
  </div>;
}
