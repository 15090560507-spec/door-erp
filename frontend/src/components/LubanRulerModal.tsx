"use client";

import { LUBAN_BIG_SECTIONS, LUBAN_CYCLE, lubanResult } from "@/lib/lubanRuler";

interface Props {
  open: boolean;
  width: number;
  height: number;
  onClose: () => void;
}

function ResultCard({ label, value }: { label: string; value: number }) {
  const result = lubanResult(value);
  return (
    <div className="rounded-lg border border-[#E5E5EA] bg-[#FAFAFC] p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[12px] text-[#8E8E93]">{label}</div>
          <div className="mt-1 text-[24px] font-semibold tabular-nums text-[#1C1C1E]">{value > 0 ? `${value} mm` : "未计算"}</div>
        </div>
        {result && value > 0 && (
          <div className={`min-w-24 rounded-md px-3 py-2 text-center ${result.auspicious ? "bg-[#34C759]/10 text-[#248A3D]" : "bg-[#FF3B30]/10 text-[#C9342D]"}`}>
            <div className="text-[22px] font-semibold">{result.bigWord}</div>
            <div className="text-[12px]">{result.smallWord} · {result.auspicious ? "吉" : "凶"}</div>
          </div>
        )}
      </div>
      {result && value > 0 && (
        <div className="mt-3 text-[11px] text-[#8E8E93]">
          本周期位置 {result.cyclePosition.toFixed(1)}mm，对应区间 {result.intervalStart.toFixed(1)}-{result.intervalEnd.toFixed(1)}mm
        </div>
      )}
    </div>
  );
}

export default function LubanRulerModal({ open, width, height, onClose }: Props) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4" onMouseDown={onClose}>
      <div className="w-full max-w-3xl rounded-xl bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#E5E5EA] px-5 py-4">
          <div>
            <h3 className="text-[16px] font-semibold text-[#1C1C1E]">鲁班尺见光区间</h3>
            <p className="mt-0.5 text-[12px] text-[#8E8E93]">按 429mm 周期，区间左闭右开。</p>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭" className="text-[22px] leading-none text-[#8E8E93] hover:text-[#1C1C1E]">×</button>
        </div>
        <div className="space-y-4 p-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ResultCard label="见光宽" value={width} />
            <ResultCard label="见光高" value={height} />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between text-[12px] text-[#8E8E93]"><span>一个完整周期</span><span>0-{LUBAN_CYCLE}mm</span></div>
            <div className="grid grid-cols-8 overflow-hidden rounded-md border border-[#E5E5EA]">
              {LUBAN_BIG_SECTIONS.map((section, index) => (
                <div key={section.name} className={`min-w-0 px-1 py-3 text-center ${section.auspicious ? "bg-[#34C759]/10 text-[#248A3D]" : "bg-[#FF3B30]/10 text-[#C9342D]"}`}>
                  <div className="font-semibold">{section.name}</div>
                  <div className="mt-1 text-[10px]">{(index * LUBAN_CYCLE / 8).toFixed(1)}-{((index + 1) * LUBAN_CYCLE / 8).toFixed(1)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
