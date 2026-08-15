"use client";

import { LUBAN_BIG_SECTIONS, LUBAN_CYCLE, LUBAN_SMALL_SEGMENTS } from "@/lib/lubanRuler";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function LubanRulerModal({ open, onClose }: Props) {
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
        <div className="p-5">
          <div className="mb-2 flex items-center justify-between text-[12px] text-[#8E8E93]"><span>一个完整周期</span><span>0-{LUBAN_CYCLE}mm</span></div>
          <div className="overflow-x-auto rounded-md border border-[#E5E5EA]">
            <div className="grid min-w-[920px] grid-cols-8">
              {LUBAN_BIG_SECTIONS.map((section, sectionIndex) => (
                <div key={section.name} className="border-r border-[#E5E5EA] last:border-r-0">
                  <div className={`px-2 py-2 text-center ${section.auspicious ? "bg-[#34C759]/10 text-[#248A3D]" : "bg-[#FF3B30]/10 text-[#C9342D]"}`}>
                    <div className="text-[18px] font-semibold">{section.name}</div>
                    <div className="text-[10px]">{section.auspicious ? "吉" : "凶"}</div>
                  </div>
                  {LUBAN_SMALL_SEGMENTS.slice(sectionIndex * 4, sectionIndex * 4 + 4).map((segment) => (
                    <div key={segment.smallWord} className="border-t border-[#E5E5EA] px-1.5 py-2 text-center">
                      <div className="text-[13px] font-medium text-[#1C1C1E]">{segment.smallWord}</div>
                      <div className="mt-0.5 whitespace-nowrap text-[9px] tabular-nums text-[#8E8E93]">
                        {segment.intervalStart.toFixed(1)}-{segment.intervalEnd.toFixed(1)}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
