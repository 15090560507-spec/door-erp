"use client";

import { memo, useState, useEffect, useRef } from "react";
import type { DoorFormData } from "@/lib/types";
import {
  DOOR_TYPES, KX_OPTIONS, NK_OPTIONS, THRESHOLD_OPTIONS,
  QC_OPTIONS, QC_SHAPE_OPTIONS, BZ_OPTIONS, HYSL_OPTIONS,
  MATERIALS, HANDLES, LOCKS, FINGERPRINT_LOCKS, HINGES, COLOR_PRESETS,
  TRIM_STYLES, DOOR_STYLES, DOOR_PANEL_STYLES, DOOR_PANEL_PRESETS, PANEL_FILL_OPTIONS,
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

const Select = memo(function Select({ label, value, options, onChange, required }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void; required?: boolean;
}) {
  return (
    <div>
      <label className="block text-[13px] font-medium text-[#8E8E93] mb-0.5">
        {required && <span className="text-[#FF3B30] mr-0.5">*</span>}{label}
      </label>
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

  const o = (key: string, fallback: string[]) => {
    const configured = opts?.[key] || [];
    return Array.from(new Set([...fallback, ...configured])).filter(Boolean);
  };

  const set = <K extends keyof DoorFormData>(key: K, value: DoorFormData[K]) => {
    onChange({ ...data, [key]: value });
  };
  const setField = (key: keyof DoorFormData, value: string | number | boolean) => {
    onChange({ ...data, [key]: value });
  };
  const frameWidth = Number(data.dw || 0);
  const frameHeight = Number(data.dh || 0);
  const frontOuterSideWidth = data.has_outer
    ? Number(data.trim_front_in || 0)
    : data.has_outer_portal
      ? Number(data.outer_portal_pillar_width || 0)
      : 0;
  const frontOuterTopHeight = data.has_outer
    ? Number(data.trim_front_in || 0)
    : data.has_outer_portal
      ? Number(data.outer_portal_header_height || 0)
      : 0;
  const innerTrimWidth = data.has_inner ? Number(data.trim_back_in || 0) : 0;
  const outerWidth = frameWidth + (frontOuterSideWidth + innerTrimWidth) * 2;
  const outerHeight = frameHeight + frontOuterTopHeight + innerTrimWidth;
  const frameArea = frameWidth > 0 && frameHeight > 0 ? frameWidth * frameHeight / 1000000 : 0;
  const outerArea = outerWidth > 0 && outerHeight > 0 ? outerWidth * outerHeight / 1000000 : 0;
  const trimArea = Math.max(0, outerArea - frameArea);
  const panelStyle = data.door_panel_style || "无造型";
  const panelPreset = data.panel_preset || "";
  const hasChildPanel = ["子母门", "两定两开", "四开门", "折叠四开门"].includes(data.door_type);
  const childPanelStyles = ["", ...DOOR_PANEL_STYLES];
  const usesOffsetX = (style: string) => ["两列式布局", "H型布局", "H+型布局"].includes(style);
  const usesThreeColumnPanel = (style: string) => style === "三列式布局";
  const usesHPanel = (style: string) => ["H型布局", "H+型布局"].includes(style);
  const usesHPlusPanel = (style: string) => style === "H+型布局";
  const usesDiscPanel = (style: string) => style === "圆盘造型";
  const panelPresetSummary: Record<string, string> = {
    "紫荆花款": "正面：A区紫荆花150mm + B区竖条；反面：中间B区竖条100mm。",
    "钱币款": "正面：A区钱币款150mm + B区竖条；反面：中间B区竖条100mm。",
    "竖条款": "正面：A区空白150mm + B区竖条；反面：中间B区竖条100mm。",
    "流星雨款": "正面：A区流星雨150mm + B区斜实虚；反面：中间B区竖条100mm。",
    "四方纳福款": "正面：A区四方纳福150mm + B区正实虚；反面：中间B区竖条100mm。",
  };
  const applyPanelPreset = (preset: string) => {
    const frontFillA: Record<string, string> = {
      "紫荆花款": "紫荆花",
      "钱币款": "钱币款",
      "竖条款": "",
      "流星雨款": "流星雨",
      "四方纳福款": "四方纳福",
    };
    const frontFillB: Record<string, string> = {
      "紫荆花款": "竖条",
      "钱币款": "竖条",
      "竖条款": "竖条",
      "流星雨款": "斜实虚",
      "四方纳福款": "正实虚",
    };
    if (!preset) {
      onChange({ ...data, panel_preset: "" });
      return;
    }
    onChange({
      ...data,
      panel_preset: preset,
      door_panel_style: "两列式布局",
      panel_lock_offset_x: 150,
      panel_fill_a: frontFillA[preset] || "",
      panel_fill_b: frontFillB[preset] || "",
      panel_fill_c: "",
      back_door_panel_style: "三列式布局",
      back_panel_three_col_a: 0,
      back_panel_three_col_b: 100,
      back_panel_three_col_c: 0,
      back_panel_fill_a: "",
      back_panel_fill_b: "竖条",
      back_panel_fill_c: "",
    });
  };
  const applyFrameDefaults = (next: DoorFormData): DoorFormData => {
    if (next.door_type === "单门") {
      const rightOpen = next.sel_kx !== "左开";
      return {
        ...next,
        fw_left_str: rightOpen ? "55/85" : "55/62",
        fw_right_str: rightOpen ? "55/62" : "55/85",
        fw_top_str: "55/75",
        th_str: "55/75",
      };
    }
    if (["对开门", "子母门", "两定两开", "四开门", "折叠四开门"].includes(next.door_type)) {
      return { ...next, fw_left_str: "55/62", fw_right_str: "55/62", fw_top_str: "55/75", th_str: "55/75" };
    }
    return next;
  };

  const renderPanelControls = ({
    title,
    styleKey,
    style,
    styleOptions,
    lockKey,
    hingeKey,
    middleKey,
    plusAKey,
    plusBKey,
    threeAKey,
    threeBKey,
    threeCKey,
    fillAKey,
    fillBKey,
    fillCKey,
    discRadiusKey,
  }: {
    title: string;
    styleKey: keyof DoorFormData;
    style: string;
    styleOptions: string[];
    lockKey: keyof DoorFormData;
    hingeKey: keyof DoorFormData;
    middleKey: keyof DoorFormData;
    plusAKey: keyof DoorFormData;
    plusBKey: keyof DoorFormData;
    threeAKey: keyof DoorFormData;
    threeBKey: keyof DoorFormData;
    threeCKey: keyof DoorFormData;
    fillAKey: keyof DoorFormData;
    fillBKey: keyof DoorFormData;
    fillCKey: keyof DoorFormData;
    discRadiusKey: keyof DoorFormData;
  }) => (
    <div className="col-span-2 rounded-lg border border-[#E5E5EA] bg-[#FAFAFC] p-3">
      <div className="grid grid-cols-2 gap-3">
        <Select
          label={`${title}样式`}
          value={style}
          options={styleOptions}
          onChange={(v) => setField(styleKey, v)}
        />
        {usesOffsetX(style) && (
          <Input
            label={`${title}锁边偏移X(mm)`}
            value={(data[lockKey] as number) ?? 180}
            type="number"
            onChange={(v) => setField(lockKey, Number(v))}
          />
        )}
        {usesThreeColumnPanel(style) && (
          <>
            <Input
              label={`${title}A锁边区宽(mm)`}
              value={(data[threeAKey] as number) ?? 0}
              type="number"
              onChange={(v) => setField(threeAKey, Number(v))}
            />
            <Input
              label={`${title}B中间区宽(mm)`}
              value={(data[threeBKey] as number) ?? 0}
              type="number"
              onChange={(v) => setField(threeBKey, Number(v))}
            />
            <Input
              label={`${title}C合页区宽(mm)`}
              value={(data[threeCKey] as number) ?? 0}
              type="number"
              onChange={(v) => setField(threeCKey, Number(v))}
            />
          </>
        )}
        {(style === "两列式布局" || style === "三列式布局") && (
          <>
            <Select
              label={`${title}A区填充`}
              value={(data[fillAKey] as string) || ""}
              options={PANEL_FILL_OPTIONS}
              onChange={(v) => setField(fillAKey, v)}
            />
            <Select
              label={`${title}B区填充`}
              value={(data[fillBKey] as string) || ""}
              options={PANEL_FILL_OPTIONS}
              onChange={(v) => setField(fillBKey, v)}
            />
            {style === "三列式布局" && (
              <Select
                label={`${title}C区填充`}
                value={(data[fillCKey] as string) || ""}
                options={PANEL_FILL_OPTIONS}
                onChange={(v) => setField(fillCKey, v)}
              />
            )}
          </>
        )}
        {usesHPanel(style) && (
          <>
            <Input
              label={`${title}合页边偏移Y(mm)`}
              value={(data[hingeKey] as number) ?? 100}
              type="number"
              onChange={(v) => setField(hingeKey, Number(v))}
            />
            <Input
              label={`${title}中区上下偏移Z(mm)`}
              value={(data[middleKey] as number) ?? 180}
              type="number"
              onChange={(v) => setField(middleKey, Number(v))}
            />
          </>
        )}
        {usesHPlusPanel(style) && (
          <>
            <Input
              label={`${title}H+上偏移A(mm)`}
              value={(data[plusAKey] as number) ?? 350}
              type="number"
              onChange={(v) => setField(plusAKey, Number(v))}
            />
            <Input
              label={`${title}H+上偏移B(mm)`}
              value={(data[plusBKey] as number) ?? 100}
              type="number"
              onChange={(v) => setField(plusBKey, Number(v))}
            />
          </>
        )}
        {usesDiscPanel(style) && (
          <Input
            label={`${title}圆盘半径(mm)`}
            value={(data[discRadiusKey] as number) ?? 120}
            type="number"
            onChange={(v) => setField(discRadiusKey, Number(v))}
          />
        )}
      </div>
    </div>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 左列：订单信息 + 材质 */}
      <div className="space-y-4">
        <Card title="订单基础信息">
          <div className="grid grid-cols-2 gap-3">
            <Input label="订货单位" required value={data.dhdw} onChange={(v) => set("dhdw", v)} />
            <Input label="项目名称" value={data.gdmc} onChange={(v) => set("gdmc", v)} />
            <Input label="订单号" value={data.ddh} onChange={(v) => set("ddh", v)} />
            <Input label="交期" type="date" value={(data.dhrq || "").replace(/\./g, "-")} onChange={(v) => set("dhrq", v)} />
            <Input label="数量(樘)" required value={data.sl} onChange={(v) => set("sl", v)} />
            <Input label="制单人" value={data.hhxd} onChange={(v) => set("hhxd", v)} />
          </div>
        </Card>

        <Card title="材质与外观">
          <div className="grid grid-cols-2 gap-3">
            <Combobox label="制作材料" required value={data.zzcl} options={o("MATERIALS", MATERIALS)} onChange={(v) => set("zzcl", v)} />
            <Combobox label="颜色" required value={data.ys} options={o("COLOR_PRESETS", COLOR_PRESETS)} onChange={(v) => set("ys", v)} />
            <Combobox label="正面款式" required value={data.zmks} options={o("DOOR_STYLES", DOOR_STYLES)} onChange={(v) => set("zmks", v)} />
            <Combobox label="反面款式" required value={data.fmks} options={o("DOOR_STYLES", DOOR_STYLES)} onChange={(v) => set("fmks", v)} />
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
          <Select
            label="门型"
            value={data.door_type}
            options={o("DOOR_TYPES", DOOR_TYPES)}
            onChange={(v) => onChange(applyFrameDefaults({ ...data, door_type: v }))}
          />
          <div className="flex gap-6 mt-3">
            <div className="flex gap-4">
              {o("KX_OPTIONS", KX_OPTIONS).map((opt) => (
                <label key={opt} className="flex items-center gap-1.5 text-[13px] font-medium text-[#8E8E93] cursor-pointer">
                  <input type="radio" name="kx" checked={data.sel_kx === opt} onChange={() => onChange(applyFrameDefaults({ ...data, sel_kx: opt }))} />
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
          <div className="flex gap-3 mt-3">
            <Select label="气窗" value={data.sel_qc} options={o("QC_OPTIONS", QC_OPTIONS)} onChange={(v) => set("sel_qc", v)} />
            <Checkbox label="门楣" checked={data.has_mm} onChange={(v) => set("has_mm", v)} />
            <Checkbox label="立柱" checked={data.has_pillar} onChange={(v) => onChange({ ...data, has_pillar: v, pillar_width_str: v && (!data.pillar_width_str || data.pillar_width_str === "55/70") ? "55/85" : data.pillar_width_str })} />
            <Checkbox label="连体门" checked={data.is_integrated_door} onChange={(v) => set("is_integrated_door", v)} />
            <Checkbox label="圆弧门" checked={data.is_arch_door} onChange={(v) => set("is_arch_door", v)} />
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3">
            {data.is_arch_door && (
              <Input label="起弧高度" value={data.arch_spring_height} type="number" onChange={(v) => set("arch_spring_height", Number(v))} />
            )}
            {data.sel_qc !== "无" && (
              <>
                <Input label="气窗高" value={data.qc_height} type="number" onChange={(v) => set("qc_height", Number(v))} />
                <Select label="气窗形状" value={data.qc_shape} options={QC_SHAPE_OPTIONS} onChange={(v) => set("qc_shape", v)} />
              </>
            )}
            {data.has_mm && (
              <Input label="门楣高" value={data.mm_height} type="number" onChange={(v) => set("mm_height", Number(v))} />
            )}
          </div>
          {data.has_pillar && (
            <Input label="立柱宽(小/大)" value={data.pillar_width_str} onChange={(v) => set("pillar_width_str", v)} />
          )}
          {data.is_integrated_door && (
            <div className="grid grid-cols-2 gap-3 mt-3">
              <Input label="封板高度" value={data.integrated_panel_height} type="number" onChange={(v) => set("integrated_panel_height", Number(v))} />
              <Input label="封板压框尺寸" value={data.integrated_press_top_rail} type="number" onChange={(v) => set("integrated_press_top_rail", Number(v))} />
              <Input label="上方玻璃高度" value={data.integrated_glass_height} type="number" onChange={(v) => set("integrated_glass_height", Number(v))} />
            </div>
          )}
        </Card>

        <Card title="尺寸输入中心">
          <div className="flex flex-wrap gap-4">
            <Checkbox label="切换为见光尺寸" checked={data.use_light_size} onChange={(v) => set("use_light_size", v)} />
            {!data.use_light_size && (
              <Checkbox label="标注见光尺寸" checked={data.mark_light_size} onChange={(v) => set("mark_light_size", v)} />
            )}
          </div>
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
          {["四开门", "折叠四开门", "两定两开"].includes(data.door_type) && (
            <Input label="中门单扇宽" value={data.mid_door_width} type="number" onChange={(v) => set("mid_door_width", Number(v))} />
          )}
        </Card>

        <details className="bg-white rounded-xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-5 cursor-pointer">
          <summary className="text-[17px] font-semibold text-[#1C1C1E] pb-2.5 border-b border-[#F2F2F7] select-none">
            门缝设置 <span className="text-[13px] font-normal text-[#8E8E93] ml-2">
              {data.left_gap}/{data.right_gap}/{data.top_gap}/{data.bottom_gap}
              {["对开门", "子母门", "四开门", "折叠四开门", "两定两开"].includes(data.door_type) && `/${data.middle_gap}`} mm
            </span>
          </summary>
          <div className="grid grid-cols-2 gap-3 mt-4">
            <Input label="左门缝(mm)" value={data.left_gap} type="number" onChange={(v) => set("left_gap", Number(v))} />
            <Input label="右门缝(mm)" value={data.right_gap} type="number" onChange={(v) => set("right_gap", Number(v))} />
            <Input label="上门缝(mm)" value={data.top_gap} type="number" onChange={(v) => set("top_gap", Number(v))} />
            <Input label="下门缝(mm)" value={data.bottom_gap} type="number" onChange={(v) => set("bottom_gap", Number(v))} />
            {["对开门", "子母门", "四开门", "折叠四开门", "两定两开"].includes(data.door_type) && (
              <Input label="中缝(mm)" value={data.middle_gap} type="number" onChange={(v) => set("middle_gap", Number(v))} />
            )}
          </div>
        </details>

        <details className="bg-white rounded-xl border border-black/5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-5 cursor-pointer">
          <summary className="text-[17px] font-semibold text-[#1C1C1E] pb-2.5 border-b border-[#F2F2F7] select-none">
            门板设置
            <span className="text-[13px] font-normal text-[#8E8E93] ml-2">
              {panelPreset || panelStyle}
            </span>
          </summary>
          <div className="grid grid-cols-2 gap-3 mt-4">
            <Select
              label="固定款式"
              value={panelPreset}
              options={DOOR_PANEL_PRESETS}
              onChange={applyPanelPreset}
            />
            {panelPreset ? (
              <div className="col-span-2 rounded-lg border border-[#E5E5EA] bg-[#FAFAFC] p-3 text-sm text-[#3A3A3C]">
                {panelPresetSummary[panelPreset] || "已按固定款式自动套用门板设置。"}
              </div>
            ) : (
              <>
                {renderPanelControls({
                  title: "正面门板",
                  styleKey: "door_panel_style",
                  style: panelStyle,
                  styleOptions: DOOR_PANEL_STYLES,
                  lockKey: "panel_lock_offset_x",
                  hingeKey: "panel_hinge_offset_y",
                  middleKey: "panel_middle_offset_z",
                  plusAKey: "panel_plus_offset_a",
                  plusBKey: "panel_plus_offset_b",
                  threeAKey: "panel_three_col_a",
                  threeBKey: "panel_three_col_b",
                  threeCKey: "panel_three_col_c",
                  fillAKey: "panel_fill_a",
                  fillBKey: "panel_fill_b",
                  fillCKey: "panel_fill_c",
                  discRadiusKey: "panel_disc_radius",
                })}
                {renderPanelControls({
                  title: "反面门板",
                  styleKey: "back_door_panel_style",
                  style: data.back_door_panel_style || "无造型",
                  styleOptions: DOOR_PANEL_STYLES,
                  lockKey: "back_panel_lock_offset_x",
                  hingeKey: "back_panel_hinge_offset_y",
                  middleKey: "back_panel_middle_offset_z",
                  plusAKey: "back_panel_plus_offset_a",
                  plusBKey: "back_panel_plus_offset_b",
                  threeAKey: "back_panel_three_col_a",
                  threeBKey: "back_panel_three_col_b",
                  threeCKey: "back_panel_three_col_c",
                  fillAKey: "back_panel_fill_a",
                  fillBKey: "back_panel_fill_b",
                  fillCKey: "back_panel_fill_c",
                  discRadiusKey: "back_panel_disc_radius",
                })}
                {hasChildPanel && renderPanelControls({
                  title: "子门门板",
                  styleKey: "child_door_panel_style",
                  style: data.child_door_panel_style || "",
                  styleOptions: childPanelStyles,
                  lockKey: "child_panel_lock_offset_x",
                  hingeKey: "child_panel_hinge_offset_y",
                  middleKey: "child_panel_middle_offset_z",
                  plusAKey: "child_panel_plus_offset_a",
                  plusBKey: "child_panel_plus_offset_b",
                  threeAKey: "child_panel_three_col_a",
                  threeBKey: "child_panel_three_col_b",
                  threeCKey: "child_panel_three_col_c",
                  fillAKey: "child_panel_fill_a",
                  fillBKey: "child_panel_fill_b",
                  fillCKey: "child_panel_fill_c",
                  discRadiusKey: "child_panel_disc_radius",
                })}
              </>
            )}
          </div>
        </details>

        <Card title="边框与下槛截面">
          <div className="grid grid-cols-2 gap-3">
            <Input label="左框宽 (小/大)" value={data.fw_left_str} onChange={(v) => set("fw_left_str", v)} />
            <Input label="右框宽 (小/大)" value={data.fw_right_str} onChange={(v) => set("fw_right_str", v)} />
            <Input label="上框宽 (小/大)" value={data.fw_top_str} onChange={(v) => set("fw_top_str", v)} />
            <Select label="下槛方案" value={data.threshold_type} options={o("THRESHOLD_OPTIONS", THRESHOLD_OPTIONS)} onChange={(v) => {
              onChange({ ...data, threshold_type: v, has_dj: v === "吊脚" });
            }} />
          </div>
          {data.threshold_type === "高低槛" ? (
            <Input label="下槛高度 (低/高)" value={data.th_str} onChange={(v) => set("th_str", v)} />
          ) : data.threshold_type === "平底槛" ? (
            <Input label="平底槛厚度(mm)" value={data.pdk} onChange={(v) => set("pdk", v)} />
          ) : (
            <Input label="吊脚高度(mm)" required value={data.dj_height} type="number" onChange={(v) => {
              onChange({ ...data, dj_height: Number(v), has_dj: true });
            }} />
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
            <Combobox label="指纹锁" required value={data.fingerprint_lock} options={o("FINGERPRINT_LOCKS", FINGERPRINT_LOCKS)} onChange={(v) => set("fingerprint_lock", v)} />
            <Input label="拉手尺寸" value={data.handle_size} placeholder="如 40*800" onChange={(v) => set("handle_size", v)} />
            <Combobox label="合页样式" required value={data.sel_hys} options={o("HINGES", HINGES)} onChange={(v) => set("sel_hys", v)} />
          </div>
          <div className="mt-3">
            <Select label="单扇合页数量" value={data.hysl} options={o("HYSL_OPTIONS", HYSL_OPTIONS)} onChange={(v) => set("hysl", v)} />
          </div>
        </Card>

        <Card title="包套与附加件">
          <div className="flex gap-4 mb-3">
            <Checkbox label="外包套" checked={data.has_outer} onChange={(v) => onChange({ ...data, has_outer: v, has_outer_portal: v ? false : data.has_outer_portal })} />
            <Checkbox label="外门头门柱" checked={data.has_outer_portal} onChange={(v) => onChange({ ...data, has_outer_portal: v, has_outer: v ? false : data.has_outer })} />
            <Checkbox label="内包套" checked={data.has_inner} onChange={(v) => set("has_inner", v)} />
          </div>
          {data.has_outer && (
            <div className="grid grid-cols-3 gap-3">
              <Input label="外包套宽" required value={data.trim_front_in} type="number" onChange={(v) => set("trim_front_in", Number(v))} />
              <Input label="正面压框" value={data.overlap_front} type="number" onChange={(v) => set("overlap_front", Number(v))} />
              <Combobox label="外包套款式" required value={data.trim_style_outer} options={["", ...o("TRIM_STYLES", TRIM_STYLES)]} onChange={(v) => set("trim_style_outer", v)} />
            </div>
          )}
          {data.has_outer_portal && (
            <div className="grid grid-cols-3 gap-3">
              <Input label="门柱宽度" required value={data.outer_portal_pillar_width} type="number" onChange={(v) => set("outer_portal_pillar_width", Number(v))} />
              <Input label="门头高度" required value={data.outer_portal_header_height} type="number" onChange={(v) => set("outer_portal_header_height", Number(v))} />
              <Input label="正面压框" value={data.overlap_front} type="number" onChange={(v) => set("overlap_front", Number(v))} />
            </div>
          )}
          {data.has_inner && (
            <div className="grid grid-cols-3 gap-3 mt-3">
              <Input label="内包套宽" required value={data.trim_back_in} type="number" onChange={(v) => set("trim_back_in", Number(v))} />
              <Input label="反面压框" value={data.overlap_back} type="number" onChange={(v) => set("overlap_back", Number(v))} />
              <Combobox label="内包套款式" required value={data.trim_style_inner} options={["", ...o("TRIM_STYLES", TRIM_STYLES)]} onChange={(v) => set("trim_style_inner", v)} />
            </div>
          )}
          <div className="mt-3 rounded-lg border border-[#E5E5EA] bg-[#FAFAFC] p-3 text-[13px] text-[#3A3A3C] space-y-1.5">
            <div>门框规格：{frameWidth || 0} x {frameHeight || 0} = {frameArea.toFixed(3)} m2</div>
            <div>外围规格：{outerWidth || 0} x {outerHeight || 0} = {outerArea.toFixed(3)} m2</div>
            <div>包套面积：{trimArea.toFixed(3)} m2</div>
          </div>
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
