"use client";

import { useId } from "react";
import { Minus, Plus } from "lucide-react";

export default function QuoteDoorQuantity({ value = 1, onChange, label }: {
  value?: number; onChange: (quantity: number) => void; label: string;
}) {
  const id = useId();
  const valid = Number.isSafeInteger(value) && value >= 1;
  return <div className="shrink-0">
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-[13px] font-medium text-[#007AFF]">樘数</label>
      <div className="flex h-9 items-center overflow-hidden rounded-md border border-[#007AFF] bg-[#007AFF]/5">
        <button type="button" aria-label={`${label}减少一樘`} title="减少一樘" disabled={!valid || value <= 1} onClick={() => onChange(value - 1)} className="grid h-9 w-8 shrink-0 place-items-center text-[#007AFF] hover:bg-[#007AFF]/10 disabled:opacity-30"><Minus size={15}/></button>
        <input id={id} aria-label={`${label}樘数`} aria-invalid={!valid} aria-describedby={!valid ? `${id}-error` : undefined} type="number" min="1" step="1" value={Number.isFinite(value) ? value : ""} onChange={(event) => onChange(event.target.value === "" ? NaN : Number(event.target.value))} className="h-9 w-16 min-w-0 border-x border-[#007AFF]/20 bg-white px-1 text-center text-[14px] tabular-nums outline-offset-[-2px] [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"/>
        <button type="button" aria-label={`${label}增加一樘`} title="增加一樘" disabled={!valid || value >= Number.MAX_SAFE_INTEGER} onClick={() => onChange(value + 1)} className="grid h-9 w-8 shrink-0 place-items-center text-[#007AFF] hover:bg-[#007AFF]/10 disabled:opacity-30"><Plus size={15}/></button>
      </div><span className="text-[13px]">樘</span>
    </div>
    {!valid && <p id={`${id}-error`} role="alert" className="mt-1 text-[12px] text-[#C93531]">樘数须为大于 0 的整数</p>}
  </div>;
}
