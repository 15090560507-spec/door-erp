"use client";

import { useEffect, useMemo, useState } from "react";
import {
  LubanAdjustment,
  LubanContinuousInterval,
  lubanContinuousResult,
  lubanNearbyIntervals,
  nearestAuspiciousAdjustments,
} from "@/lib/lubanRuler";

interface Props {
  open: boolean;
  width: number;
  height: number;
  onClose: () => void;
}

type DimensionKey = "width" | "height";

function formatMillimeters(value: number) {
  return Number(value.toFixed(1));
}

function integerInterval(interval: LubanContinuousInterval) {
  return `${Math.ceil(interval.intervalStart)}-${Math.ceil(interval.intervalEnd) - 1}mm`;
}

function AdjustmentItem({ direction, adjustment }: { direction: "向下" | "向上"; adjustment: LubanAdjustment | null }) {
  if (!adjustment) {
    return <div className="border-t border-[#E5E5EA] px-4 py-3 text-[12px] text-[#8E8E93] first:border-t-0">{direction}暂无可用吉区</div>;
  }
  return (
    <div className="flex items-center justify-between gap-3 border-t border-[#E5E5EA] px-4 py-3 first:border-t-0">
      <div>
        <div className="text-[12px] text-[#8E8E93]">{direction}最近吉区</div>
        <div className="mt-0.5 text-[13px] font-medium text-[#1C1C1E]">
          {adjustment.interval.bigWord} · {adjustment.interval.smallWord}
          <span className="ml-2 font-normal text-[#248A3D]">{integerInterval(adjustment.interval)}</span>
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="text-[18px] font-semibold tabular-nums text-[#007AFF]">{adjustment.target}mm</div>
        <div className="text-[11px] tabular-nums text-[#8E8E93]">
          {adjustment.delta > 0 ? "+" : ""}{formatMillimeters(adjustment.delta)}mm
        </div>
      </div>
    </div>
  );
}

export default function LubanRulerModal({ open, width, height, onClose }: Props) {
  const [activeDimension, setActiveDimension] = useState<DimensionKey>("width");

  useEffect(() => {
    if (open) setActiveDimension("width");
  }, [open]);

  const value = activeDimension === "width" ? width : height;
  const current = useMemo(() => lubanContinuousResult(value), [value]);
  const nearby = useMemo(() => lubanNearbyIntervals(value, 5), [value]);
  const adjustments = useMemo(() => nearestAuspiciousAdjustments(value), [value]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4" onMouseDown={onClose}>
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#E5E5EA] px-5 py-4">
          <div>
            <h3 className="text-[16px] font-semibold text-[#1C1C1E]">鲁班尺见光区间</h3>
            <p className="mt-0.5 text-[12px] text-[#8E8E93]">当前尺寸居中显示，区间按 429mm 周期循环。</p>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭" className="text-[22px] leading-none text-[#8E8E93] hover:text-[#1C1C1E]">×</button>
        </div>

        <div className="border-b border-[#E5E5EA] px-5 py-3">
          <div className="grid grid-cols-2 rounded-md bg-[#F2F2F7] p-1">
            {([
              ["width", "见光宽", width],
              ["height", "见光高", height],
            ] as const).map(([key, label, dimensionValue]) => (
              <button
                key={key}
                type="button"
                onClick={() => setActiveDimension(key)}
                className={`min-h-9 rounded px-3 text-[13px] font-medium ${activeDimension === key ? "bg-white text-[#1C1C1E] shadow-sm" : "text-[#8E8E93]"}`}
              >
                {label} <span className="ml-1 tabular-nums">{dimensionValue > 0 ? `${formatMillimeters(dimensionValue)}mm` : "未计算"}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-y-auto p-5">
          {!current || value <= 0 ? (
            <div className="py-14 text-center text-[13px] text-[#8E8E93]">当前尺寸未计算</div>
          ) : (
            <div className="space-y-4">
              <section className={`flex items-center justify-between gap-4 border px-4 py-3 ${current.auspicious ? "border-[#34C759]/30 bg-[#34C759]/10" : "border-[#FF3B30]/30 bg-[#FF3B30]/10"}`}>
                <div>
                  <div className="text-[12px] text-[#8E8E93]">当前{activeDimension === "width" ? "见光宽" : "见光高"}</div>
                  <div className="mt-0.5 flex items-baseline gap-3">
                    <strong className="text-[25px] tabular-nums text-[#1C1C1E]">{formatMillimeters(value)}mm</strong>
                    <span className={`text-[13px] font-semibold ${current.auspicious ? "text-[#248A3D]" : "text-[#C9342D]"}`}>
                      {current.auspicious ? "吉" : "凶"}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-[22px] font-semibold ${current.auspicious ? "text-[#248A3D]" : "text-[#C9342D]"}`}>
                    {current.bigWord} · {current.smallWord}
                  </div>
                  <div className="mt-1 text-[11px] tabular-nums text-[#8E8E93]">整数参考 {integerInterval(current)}</div>
                </div>
              </section>

              {!current.auspicious && (
                <section className="border border-[#E5E5EA]">
                  <div className="bg-[#FAFAFC] px-4 py-2 text-[12px] font-medium text-[#1C1C1E]">邻近吉区调整建议</div>
                  <AdjustmentItem direction="向下" adjustment={adjustments.down} />
                  <AdjustmentItem direction="向上" adjustment={adjustments.up} />
                </section>
              )}

              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-[13px] font-semibold text-[#1C1C1E]">当前尺寸附近区间</h4>
                  <span className="text-[11px] text-[#8E8E93]">整数毫米参考</span>
                </div>
                <div className="overflow-hidden border border-[#E5E5EA]">
                  {nearby.map((interval) => {
                    const isCurrent = interval.index === current.index;
                    return (
                      <div
                        key={interval.index}
                        className={`grid min-h-10 grid-cols-[minmax(105px,1.3fr)_48px_minmax(64px,1fr)_44px] items-center gap-2 border-t border-[#E5E5EA] px-3 py-2 text-[12px] first:border-t-0 ${isCurrent ? "bg-[#007AFF]/8 ring-1 ring-inset ring-[#007AFF]/40" : "bg-white"}`}
                      >
                        <div className="tabular-nums text-[#1C1C1E]">
                          {integerInterval(interval)}
                          {isCurrent && <span className="ml-2 text-[10px] font-medium text-[#007AFF]">当前</span>}
                        </div>
                        <div className="font-semibold text-[#1C1C1E]">{interval.bigWord}</div>
                        <div className="text-[#636366]">{interval.smallWord}</div>
                        <div className={`text-right font-medium ${interval.auspicious ? "text-[#248A3D]" : "text-[#C9342D]"}`}>
                          {interval.auspicious ? "吉" : "凶"}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
