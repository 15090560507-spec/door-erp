"use client";

import { Calculator, Download, Eye, ImagePlus, Save } from "lucide-react";

type Props = {
  previewLoading: boolean;
  cadLoading: boolean;
  renderLoading: boolean;
  saving: boolean;
  quoteOpening: boolean;
  onPreview: () => void;
  onCad: () => void;
  onRender: () => void;
  onSave: () => void;
  onQuote: () => void;
};

export default function DrawingFormActions(props: Props) {
  const saving = props.saving || props.quoteOpening;
  const base = "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors disabled:cursor-wait disabled:opacity-50";
  return (
    <div data-drawing-actions className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-5">
      <button type="button" onClick={props.onPreview} disabled={props.previewLoading || props.cadLoading || saving}
        className={`${base} bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]`}>
        <Eye size={16} aria-hidden="true" />{props.previewLoading ? "正在生成预览..." : "预览 DXF"}
      </button>
      <button type="button" onClick={props.onCad} disabled={props.cadLoading || props.previewLoading || saving}
        className={`${base} border border-[#C7C7CC] bg-white text-[#1C1C1E] hover:border-[#007AFF] hover:text-[#007AFF]`}>
        <Download size={16} aria-hidden="true" />{props.cadLoading ? "生成中..." : "生成 DXF"}
      </button>
      <button type="button" onClick={props.onRender} disabled={props.renderLoading || saving}
        className={`${base} bg-[#007AFF] font-semibold text-white hover:bg-[#0065D1]`}>
        <ImagePlus size={16} aria-hidden="true" />{props.renderLoading ? "效果图生成中..." : "生成效果图"}
      </button>
      <button type="button" onClick={props.onSave} disabled={saving}
        className={`${base} bg-[#1C1C1E] font-semibold text-white hover:bg-[#3A3A3C]`}>
        <Save size={16} aria-hidden="true" />{props.saving ? "保存中..." : "保存表单"}
      </button>
      <button type="button" onClick={props.onQuote} disabled={saving}
        className={`${base} border border-[#007AFF] bg-white font-semibold text-[#007AFF] hover:bg-[#F0F6FF]`}>
        <Calculator size={16} aria-hidden="true" />{props.quoteOpening ? "正在打开报价..." : "去报价"}
      </button>
    </div>
  );
}
