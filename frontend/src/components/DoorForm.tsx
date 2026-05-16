"use client";

import { memo, useState, useEffect, useRef } from "react";
import type { DoorFormData } from "@/lib/types";
import {
  DOOR_TYPES, KX_OPTIONS, NK_OPTIONS, THRESHOLD_OPTIONS,
  QC_OPTIONS, BZ_OPTIONS, HYSL_OPTIONS,
  MATERIALS, HANDLES, LOCKS, HINGES, COLOR_PRESETS,
  TRIM_STYLES,
} from "@/lib/types";
import { loadDropdownOptions } from "@/lib/api";

interface Props {
  data: DoorFormData;
  onChange: (data: DoorFormData) => void;
  readOnly?: boolean;
  children?: React.ReactNode;
}

const Input = memo(function Input({ label, value, onChange, placeholder, type = "text", required }: {
  label: string; value: string | number; onChange: (v: string) => void;
  placeholder?: string; type?: string; required?: boolean;
}) {
  return (
    <div>
      <label className="block text-[13px] font-medium text-[#8E8E93] mb-0.5">
        {required && <span className="text-[#FF3B30] mr-0.5">*</span>}{label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)]"
      />
    </div>
  );
});

const Select = memo(function Select({ label, value, options, onChange }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-[13px] font-medium text-[#8E8E93] mb-0.5">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)]"
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
});

const Checkbox = memo(function Checkbox({ label, checked, onChange }: {
  label: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-[13px] font-medium text-[#8E8E93] cursor-pointer">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="w-4 h-4" />
      {label}
    </label>
  );
});

const Card = memo(function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-5">
      <h4 className="text-[17px] font-semibold text-[#1C1C1E] mb-4 pb-2.5 border-b border-[#F2F2F7]">{title}</h4>
      {children}
    </div>
  );
});

const Combobox = memo(function Combobox({ label, value, options, onChange, required }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void; required?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState(value);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setInputValue(value); }, [value]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = options.filter((o) => o.toLowerCase().includes(inputValue.toLowerCase()));

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-[13px] font-medium text-[#8E8E93] mb-0.5">
        {required && <span className="text-[#FF3B30] mr-0.5">*</span>}{label}
      </label>
      <input
        ref={inputRef}
        type="text"
        value={inputValue}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setInputValue(e.target.value); onChange(e.target.value); setOpen(true); }}
        onKeyDown={(e) => { if (e.key === "Escape" || e.key === "Enter") { setOpen(false); inputRef.current?.blur(); } }}
        className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)]"
      />
      {open && filtered.length > 0 && (
        <ul className="absolute z-20 left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-[#C7C7CC] rounded-md shadow-lg">
          {filtered.map((o) => (
            <li key={o} onMouseDown={(e) => { e.preventDefault(); setInputValue(o); onChange(o); setOpen(false); }}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-[#F2F2F7] transition-colors">
              {o}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
});

const DoorForm = memo(function DoorForm({ data, onChange, readOnly, children }: Props) {
  const [opts, setOpts] = useState<Record<string, string[]> | null>(null);

  useEffect(() => {
    loadDropdownOptions().then(setOpts);
  }, []);

  const o = (key: string, fallback: string[]) =>
    (opts && opts[key] && opts[key].length > 0) ? opts[key] : fallback;

  const set = <K extends keyof DoorFormData>(key: K, value: DoorFormData[K]) => {
    onChange({ ...data, [key]: value });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 左列：订单信息 + 材质 */}
      <div className="space-y-4">
        <Card title="订单基础信息">
          <div className="grid grid-cols-2 gap-3">
            <Input label="订货单位" required value={data.dhdw} onChange={(v) => set("dhdw", v)} />
            <Input label="项目名称" value={data.gdmc} onChange={(v) => set("gdmc", v)} />
            <Input label="订单号" value={data.ddh} onChange={(v) => set("ddh", v)} />
            <Input label="交期" value={data.dhrq} onChange={(v) => set("dhrq", v)} />
            <Input label="数量(樘)" required value={data.sl} onChange={(v) => set("sl", v)} />
            <Input label="制单人" value={data.hhxd} onChange={(v) => set("hhxd", v)} />
          </div>
        </Card>

        <Card title="材质与外观">
          <div className="grid grid-cols-2 gap-3">
            <Combobox label="制作材料" required value={data.zzcl} options={o("MATERIALS", MATERIALS)} onChange={(v) => set("zzcl", v)} />
            <Combobox label="颜色" required value={data.ys} options={o("COLOR_PRESETS", COLOR_PRESETS)} onChange={(v) => set("ys", v)} />
            <Input label="正面款式" value={data.zmks} onChange={(v) => set("zmks", v)} />
            <Input label="反面款式" value={data.fmks} onChange={(v) => set("fmks", v)} />
            <Input label="门扇厚度(mm)" value={data.mshd} type="number" onChange={(v) => set("mshd", Number(v))} />
            <Input label="墙厚(mm)" value={data.qh} onChange={(v) => set("qh", v)} />
          </div>
          <div className="mt-3 flex gap-6">
            {o("BZ_OPTIONS", BZ_OPTIONS).map((opt) => (
              <label key={opt} className="flex items-center gap-1.5 text-[13px] font-medium text-[#8E8E93] cursor-pointer">
                <input type="radio" name="bz" checked={data.sel_bz === opt} onChange={() => set("sel_bz", opt)} />
                {opt}
              </label>
            ))}
          </div>
        </Card>
      </div>

      {/* 中列：结构 + 尺寸 */}
      <div className="space-y-4">
        <Card title="结构与开向">
          <Select label="门型" value={data.door_type} options={o("DOOR_TYPES", DOOR_TYPES)} onChange={(v) => set("door_type", v)} />
          <div className="flex gap-6 mt-3">
            <div className="flex gap-4">
              {o("KX_OPTIONS", KX_OPTIONS).map((opt) => (
                <label key={opt} className="flex items-center gap-1.5 text-[13px] font-medium text-[#8E8E93] cursor-pointer">
                  <input type="radio" name="kx" checked={data.sel_kx === opt} onChange={() => set("sel_kx", opt)} />
                  {opt}
                </label>
              ))}
            </div>
            <div className="flex gap-4">
              {o("NK_OPTIONS", NK_OPTIONS).map((opt) => (
                <label key={opt} className="flex items-center gap-1.5 text-[13px] font-medium text-[#8E8E93] cursor-pointer">
                  <input type="radio" name="nk" checked={data.sel_nk === opt} onChange={() => set("sel_nk", opt)} />
                  {opt}
                </label>
              ))}
            </div>
          </div>
        </Card>

        <Card title="尺寸输入中心">
          <Checkbox label="切换为见光尺寸" checked={data.use_light_size} onChange={(v) => set("use_light_size", v)} />
          <div className="grid grid-cols-2 gap-3 mt-3">
            {data.use_light_size ? (
              <>
                <Input label="见光宽(W)" value={data.light_w} type="number" onChange={(v) => set("light_w", Number(v))} />
                <Input label="见光高(H)" value={data.light_h} type="number" onChange={(v) => set("light_h", Number(v))} />
              </>
            ) : (
              <>
                <Input label="洞口总宽(W)" required value={data.dw} type="number" onChange={(v) => set("dw", Number(v))} />
                <Input label="洞口总高(H)" required value={data.dh} type="number" onChange={(v) => set("dh", Number(v))} />
              </>
            )}
          </div>
          {data.door_type === "子母门" && (
            <Input label="母门单扇宽" value={data.mother_door_width} type="number" onChange={(v) => set("mother_door_width", Number(v))} />
          )}
          {["折叠四开门", "两定两开"].includes(data.door_type) && (
            <Input label="中门单扇宽" value={data.mid_door_width} type="number" onChange={(v) => set("mid_door_width", Number(v))} />
          )}
        </Card>

        <details className="bg-white rounded-xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-5 cursor-pointer">
          <summary className="text-[17px] font-semibold text-[#1C1C1E] pb-2.5 border-b border-[#F2F2F7] select-none">
            门缝设置 <span className="text-[13px] font-normal text-[#8E8E93] ml-2">
              {data.left_gap}/{data.right_gap}/{data.top_gap}/{data.bottom_gap}
              {["对开门", "子母门", "折叠四开门", "两定两开"].includes(data.door_type) && `/${data.middle_gap}`} mm
            </span>
          </summary>
          <div className="grid grid-cols-2 gap-3 mt-4">
            <Input label="左门缝(mm)" value={data.left_gap} type="number" onChange={(v) => set("left_gap", Number(v))} />
            <Input label="右门缝(mm)" value={data.right_gap} type="number" onChange={(v) => set("right_gap", Number(v))} />
            <Input label="上门缝(mm)" value={data.top_gap} type="number" onChange={(v) => set("top_gap", Number(v))} />
            <Input label="下门缝(mm)" value={data.bottom_gap} type="number" onChange={(v) => set("bottom_gap", Number(v))} />
            {["对开门", "子母门", "折叠四开门", "两定两开"].includes(data.door_type) && (
              <Input label="中缝(mm)" value={data.middle_gap} type="number" onChange={(v) => set("middle_gap", Number(v))} />
            )}
          </div>
        </details>

        <details className="bg-white rounded-xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-5 cursor-pointer">
          <summary className="text-[17px] font-semibold text-[#1C1C1E] pb-2.5 border-b border-[#F2F2F7] select-none">
            门板设置
          </summary>
          <div className="grid grid-cols-1 gap-3 mt-4">
            <Input label="锁边偏移量(mm)" value={data.lock_side_offset} type="number" onChange={(v) => set("lock_side_offset", Number(v))} />
          </div>
        </details>

        <Card title="边框与下槛截面">
          <div className="grid grid-cols-2 gap-3">
            <Input label="左框宽 (外/内)" value={data.fw_left_str} onChange={(v) => set("fw_left_str", v)} />
            <Input label="右框宽 (外/内)" value={data.fw_right_str} onChange={(v) => set("fw_right_str", v)} />
            <Input label="上框宽 (外/内)" value={data.fw_top_str} onChange={(v) => set("fw_top_str", v)} />
            <Select label="下槛方案" value={data.threshold_type} options={o("THRESHOLD_OPTIONS", THRESHOLD_OPTIONS)} onChange={(v) => set("threshold_type", v)} />
          </div>
          {data.threshold_type === "高低槛" ? (
            <Input label="下槛高度 (低/高)" value={data.th_str} onChange={(v) => set("th_str", v)} />
          ) : (
            <Input label="平底槛厚度(mm)" value={data.pdk} onChange={(v) => set("pdk", v)} />
          )}
        </Card>
      </div>

      {/* 右列：五金 + 包套 + 批注 */}
      <div className="space-y-4">
        <Card title="五金锁具">
          <div className="grid grid-cols-2 gap-3">
            <Combobox label="正面拉手" value={data.zmls} options={o("HANDLES", HANDLES)} onChange={(v) => set("zmls", v)} />
            <Combobox label="反面拉手" value={data.fmls} options={o("HANDLES", HANDLES)} onChange={(v) => set("fmls", v)} />
            <Combobox label="锁体类型" value={data.st_val} options={o("LOCKS", LOCKS)} onChange={(v) => set("st_val", v)} />
            <Combobox label="合页样式" value={data.sel_hys} options={o("HINGES", HINGES)} onChange={(v) => set("sel_hys", v)} />
          </div>
          <div className="mt-3">
            <Select label="单扇合页数量" value={data.hysl} options={o("HYSL_OPTIONS", HYSL_OPTIONS)} onChange={(v) => set("hysl", v)} />
          </div>
        </Card>

        <Card title="包套与附加件">
          <div className="flex gap-4 mb-3">
            <Checkbox label="外包套" checked={data.has_outer} onChange={(v) => set("has_outer", v)} />
            <Checkbox label="内包套" checked={data.has_inner} onChange={(v) => set("has_inner", v)} />
            {(data.has_outer || data.has_inner) && (
              <Input label="压框" value={data.overlap} type="number" onChange={(v) => set("overlap", Number(v))} />
            )}
          </div>
          {data.has_outer && (
            <div className="grid grid-cols-2 gap-3">
              <Input label="外包套宽" value={data.trim_front_in} type="number" onChange={(v) => set("trim_front_in", Number(v))} />
              <Select label="外包套款式" value={data.trim_style_outer} options={["", ...TRIM_STYLES]} onChange={(v) => set("trim_style_outer", v)} />
            </div>
          )}
          {data.has_inner && (
            <div className="grid grid-cols-2 gap-3 mt-3">
              <Input label="内包套宽" value={data.trim_back_in} type="number" onChange={(v) => set("trim_back_in", Number(v))} />
              <Select label="内包套款式" value={data.trim_style_inner} options={["", ...TRIM_STYLES]} onChange={(v) => set("trim_style_inner", v)} />
            </div>
          )}
          <div className="flex gap-3 mt-3">
            <Select label="气窗" value={data.sel_qc} options={o("QC_OPTIONS", QC_OPTIONS)} onChange={(v) => set("sel_qc", v)} />
            <Checkbox label="门楣" checked={data.has_mm} onChange={(v) => set("has_mm", v)} />
            <Checkbox label="立柱" checked={data.has_pillar} onChange={(v) => set("has_pillar", v)} />
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3">
            {data.sel_qc !== "无" && (
              <Input label="气窗高" value={data.qc_height} type="number" onChange={(v) => set("qc_height", Number(v))} />
            )}
            {data.has_mm && (
              <Input label="门楣高" value={data.mm_height} type="number" onChange={(v) => set("mm_height", Number(v))} />
            )}
          </div>
          {data.has_pillar && (
            <Input label="立柱宽(外/内)" value={data.pillar_width_str} onChange={(v) => set("pillar_width_str", v)} />
          )}
        </Card>

        <Card title="车间生产批注">
          <textarea
            value={data.sm}
            onChange={(e) => set("sm", e.target.value)}
            placeholder="补充图纸外的额外加工要求..."
            rows={3}
            className="w-full px-3 py-2 text-sm rounded-md bg-[#FAFAFC] border border-[#C7C7CC] outline-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.15)] resize-none"
          />
        </Card>

        {children}
      </div>
    </div>
  );
});

export default DoorForm;
