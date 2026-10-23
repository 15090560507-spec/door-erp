"use client";

import { RotateCcw } from "lucide-react";
import { PANEL_FILL_OPTIONS, type DoorFormData } from "@/lib/types";

type DiscPrefix = "panel" | "back_panel" | "child_panel" | "child_back_panel";
const control = "w-full min-w-0 rounded-md border border-[#C7C7CC] bg-white px-3 py-2 text-sm outline-none focus:border-[#007AFF]";

export default function DiscPanelFields({ title, radiusKey, data, onChange }: {
  title: string;
  radiusKey: keyof DoorFormData;
  data: DoorFormData;
  onChange: (data: DoorFormData) => void;
}) {
  const prefix = String(radiusKey).replace(/_disc_radius$/, "") as DiscPrefix;
  const styleKey = `${prefix}_disc_style` as const;
  const centerKey = `${prefix}_disc_center_height` as const;
  const fillKey = `${prefix}_disc_outer_fill` as const;
  const style = data[styleKey] ?? "圆形";
  const field = (name: string, child: React.ReactNode) => <div className="block min-w-0 text-[13px] font-medium text-[#8E8E93]">
    <span className="mb-1 block">{title}{name}</span>{child}
  </div>;
  return <div className="col-span-2 grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
    {field("圆盘款式", <select aria-label={`${title}圆盘款式`} className={control} value={style} onChange={event => {
      const nextStyle = event.target.value;
      onChange({ ...data, [styleKey]: nextStyle,
        [radiusKey]: style === "圆形" && nextStyle !== "圆形" && data[radiusKey] === 120 ? 700 : data[radiusKey] });
    }}>
      {["圆形", "圆形牡丹花", "四叶草牡丹花"].map(value => <option key={value}>{value}</option>)}
    </select>)}
    {field("圆盘半径(mm)", <input aria-label={`${title}圆盘半径(mm)`} className={control} type="number" min="1" step="1"
      value={data[radiusKey] as number} onChange={event => onChange({ ...data, [radiusKey]: Number(event.target.value) })} />)}
    {field("圆心高度(mm)", <div className="flex min-w-0 gap-1">
      <input aria-label={`${title}圆心高度(mm)`} className={control} type="number" min="0.1" step="any"
        value={data[centerKey] ?? ""} placeholder="跟随拉手高度"
        onChange={event => onChange({ ...data, [centerKey]: event.target.value === "" ? null : Number(event.target.value) })} />
      <button type="button" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-[#C7C7CC] bg-white text-[#636366]"
        title="恢复跟随拉手高度" aria-label={`${title}恢复跟随拉手高度`} onClick={() => onChange({ ...data, [centerKey]: null })}>
        <RotateCcw size={16} />
      </button>
    </div>)}
    {field("圆盘外部填充", <select aria-label={`${title}圆盘外部填充`} className={control}
      value={data[fillKey] ?? (style === "圆形" ? "" : "竖条")}
      onChange={event => onChange({ ...data, [fillKey]: event.target.value })}>
      {PANEL_FILL_OPTIONS.map(value => <option key={value} value={value}>{value || "无填充"}</option>)}
    </select>)}
  </div>;
}
