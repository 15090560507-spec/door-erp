interface Props {
  busy: boolean;
  canExport: boolean;
  onSave: () => void;
  onExportDxf: () => void;
  onExportBom: () => void;
  onExportJson: () => void;
}

export default function ProjectActions({ busy, canExport, onSave, onExportDxf, onExportBom, onExportJson }: Props) {
  const disabled = busy || !canExport;
  const secondary = "h-9 border border-[#D1D1D6] bg-white px-4 text-[13px] font-medium text-[#1C1C1E] hover:bg-[#F2F2F7] disabled:cursor-not-allowed disabled:opacity-45";
  return (
    <div className="flex flex-wrap items-center gap-2 border border-[#D1D1D6] bg-white p-3">
      <button type="button" onClick={onSave} disabled={busy || !canExport} className="h-9 bg-[#007AFF] px-5 text-[13px] font-semibold text-white hover:bg-[#0066D6] disabled:cursor-not-allowed disabled:opacity-45">
        {busy ? "处理中..." : "保存项目"}
      </button>
      <button type="button" onClick={onExportDxf} disabled={disabled} className={secondary}>导出综合 DXF</button>
      <button type="button" onClick={onExportBom} disabled={disabled} className={secondary}>导出 BOM</button>
      <button type="button" onClick={onExportJson} disabled={disabled} className={secondary}>导出项目 JSON</button>
      {!canExport && <span className="ml-auto text-xs text-[#8E8E93]">请先完成有效计算</span>}
    </div>
  );
}
