"use client";

import { useState } from "react";
import { Download, FileCheck2, FileUp, RotateCcw, Upload } from "lucide-react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import {
  downloadMasterDataImportTemplate,
  executeMasterDataImport,
  previewMasterDataImport,
  rollbackMasterDataImport,
  validateMasterDataImport,
} from "@/lib/inventoryApi";
import type { MasterDataImportEntity, MasterDataImportPreview } from "@/lib/inventoryTypes";

const ENTITY_OPTIONS: Array<{ value: MasterDataImportEntity; label: string; note: string }> = [
  { value: "materials", label: "物料与商品", note: "建议先导入" },
  { value: "suppliers", label: "供应商", note: "建议第二步导入" },
  { value: "supplier_items", label: "供应商产品", note: "需已有物料和供应商编码" },
];

export default function MasterDataImportDialog({ open, onClose, onImported, notify }: { open: boolean; onClose: () => void; onImported: () => void; notify: (message: string, error?: boolean) => void }) {
  const [entityType, setEntityType] = useState<MasterDataImportEntity>("materials");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<MasterDataImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [duplicateStrategy, setDuplicateStrategy] = useState<"skip" | "update">("skip");
  const [busy, setBusy] = useState(false);

  const reset = (nextType = entityType) => {
    setEntityType(nextType);
    setFile(null);
    setPreview(null);
    setMapping({});
    setDuplicateStrategy("skip");
  };
  const upload = async () => {
    if (!file) { notify("请先选择 Excel 或 CSV 文件", true); return; }
    setBusy(true);
    try {
      const result = await previewMasterDataImport(entityType, file);
      setPreview(result);
      setMapping(result.mapping);
      notify(`已读取 ${result.batch.total_rows} 行，请检查字段映射和预检结果`);
    } catch (error) { notify(apiMessage(error, "导入文件读取失败"), true); }
    finally { setBusy(false); }
  };
  const validate = async () => {
    if (!preview) return null;
    setBusy(true);
    try {
      const result = await validateMasterDataImport(preview.batch.id, mapping, duplicateStrategy);
      setPreview(result);
      setMapping(result.mapping);
      notify(result.batch.error_rows ? `预检发现 ${result.batch.error_rows} 行错误` : `预检通过，共 ${result.batch.valid_rows} 行可执行`, Boolean(result.batch.error_rows));
      return result;
    } catch (error) { notify(apiMessage(error, "重新预检失败"), true); return null; }
    finally { setBusy(false); }
  };
  const execute = async () => {
    if (!preview) return;
    setBusy(true);
    try {
      const checked = await validateMasterDataImport(preview.batch.id, mapping, duplicateStrategy);
      setPreview(checked);
      if (checked.batch.error_rows) { notify(`仍有 ${checked.batch.error_rows} 行错误，暂未执行导入`, true); return; }
      const result = await executeMasterDataImport(preview.batch.id, checked.mapping, duplicateStrategy);
      setPreview({ ...checked, batch: result.batch });
      notify(result.message, Boolean(result.batch.error_rows));
      onImported();
    } catch (error) { notify(apiMessage(error, "基础资料导入失败"), true); }
    finally { setBusy(false); }
  };
  const rollback = async () => {
    if (!preview) return;
    setBusy(true);
    try {
      const result = await rollbackMasterDataImport(preview.batch.id);
      setPreview((current) => current ? { ...current, batch: result.batch } : current);
      notify(result.message, result.batch.status === "部分回滚");
      onImported();
    } catch (error) { notify(apiMessage(error, "导入批次回滚失败"), true); }
    finally { setBusy(false); }
  };
  const download = async () => {
    setBusy(true);
    try {
      const blob = await downloadMasterDataImportTemplate(entityType);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${ENTITY_OPTIONS.find((item) => item.value === entityType)?.label || "基础资料"}_导入模板.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) { notify(apiMessage(error, "模板下载失败"), true); }
    finally { setBusy(false); }
  };

  const finished = preview && ["已完成", "部分完成", "已回滚", "部分回滚"].includes(preview.batch.status);
  return <ViewportDialog open={open} title="外部 ERP 基础资料导入" description="先预检再写入。推荐依次导入物料、供应商、供应商产品。" size="wide" onClose={onClose} footer={<>{preview && !finished && <><button type="button" className="ui-button ui-button--secondary" disabled={busy} onClick={() => void validate()}><FileCheck2 size={15}/>重新预检</button><button type="button" className="ui-button ui-button--primary" disabled={busy || Boolean(preview.batch.error_rows)} onClick={() => void execute()}><Upload size={15}/>{busy ? "正在处理..." : "执行导入"}</button></>}{preview && ["已完成", "部分完成"].includes(preview.batch.status) && <button type="button" className="ui-button ui-button--danger" disabled={busy} onClick={() => void rollback()}><RotateCcw size={15}/>回滚本批新增</button>}<button type="button" className="ui-button ui-button--secondary" onClick={onClose}>关闭</button></>}>
    <div className="grid gap-3 md:grid-cols-[minmax(180px,0.7fr)_minmax(280px,1.3fr)_auto_auto]">
      <label className="text-xs text-[#636366]">资料类型<select value={entityType} disabled={Boolean(preview)} onChange={(event) => reset(event.target.value as MasterDataImportEntity)} className="mt-1 h-10 w-full border border-[#C7C7CC] px-2 text-sm text-[#1C1C1E]">{ENTITY_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label} · {item.note}</option>)}</select></label>
      <label className="text-xs text-[#636366]">导入文件<input type="file" accept=".xlsx,.xlsm,.csv" disabled={Boolean(preview)} onChange={(event) => setFile(event.target.files?.[0] || null)} className="mt-1 block h-10 w-full border border-[#C7C7CC] bg-white px-2 py-1.5 text-sm" /></label>
      <button type="button" disabled={busy || Boolean(preview)} onClick={() => void upload()} className="ui-button ui-button--primary self-end"><FileUp size={15}/>上传预检</button>
      <button type="button" disabled={busy} onClick={() => void download()} className="ui-button ui-button--secondary self-end"><Download size={15}/>下载模板</button>
    </div>

    {preview && <div className="mt-5 space-y-4">
      <section className="grid grid-cols-2 gap-px border border-[#E5E5EA] bg-[#E5E5EA] md:grid-cols-5"><Metric label="批次" value={preview.batch.batch_no}/><Metric label="文件行数" value={preview.batch.total_rows}/><Metric label="可执行" value={preview.batch.valid_rows}/><Metric label="错误行" value={preview.batch.error_rows} danger={preview.batch.error_rows > 0}/><Metric label="状态" value={preview.batch.status}/></section>
      {!finished && <section className="border border-[#E5E5EA]"><header className="flex flex-wrap items-center gap-3 border-b border-[#E5E5EA] bg-[#FAFAFB] px-4 py-3"><strong className="mr-auto text-sm">字段对应</strong><label className="flex items-center gap-2 text-xs text-[#636366]">重复编码<select value={duplicateStrategy} onChange={(event) => setDuplicateStrategy(event.target.value as "skip" | "update")} className="h-8 border border-[#C7C7CC] bg-white px-2 text-sm text-[#1C1C1E]"><option value="skip">跳过已有资料</option><option value="update">更新已有资料</option></select></label></header><div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">{preview.fields.map((field) => <label key={field.key} className="text-xs text-[#636366]">{field.label}{field.required && <b className="ml-1 text-[#C93531]">*</b>}<select value={mapping[field.key] || ""} onChange={(event) => setMapping((current) => ({ ...current, [field.key]: event.target.value }))} className="mt-1 h-9 w-full border border-[#C7C7CC] bg-white px-2 text-sm text-[#1C1C1E]"><option value="">不导入</option>{preview.headers.map((header) => <option key={header} value={header}>{header}</option>)}</select></label>)}</div></section>}
      <section className="border border-[#E5E5EA]"><header className="border-b border-[#E5E5EA] bg-[#FAFAFB] px-4 py-3"><strong className="text-sm">数据预览与校验</strong><span className="ml-2 text-xs text-[#8E8E93]">最多显示前 50 行</span></header><div className="divide-y divide-[#E5E5EA]">{preview.rows.slice(0, 12).map((row) => <div key={row.row_number} className="grid gap-2 px-4 py-3 md:grid-cols-[72px_1fr_260px]"><strong className="text-xs">第 {row.row_number} 行</strong><div className="flex flex-wrap gap-x-4 gap-y-1">{preview.fields.filter((field) => row.values[field.key] !== undefined && row.values[field.key] !== "").slice(0, 6).map((field) => <span key={field.key} className="text-xs text-[#636366]"><b className="font-medium text-[#303036]">{field.label}</b> {String(row.values[field.key])}</span>)}</div><div>{row.errors.map((item) => <p key={item} className="text-xs text-[#C93531]">{item}</p>)}{row.warnings.map((item) => <p key={item} className="text-xs text-[#9A6700]">{item}</p>)}{!row.errors.length && !row.warnings.length && <span className="text-xs text-[#248A3D]">校验通过</span>}</div></div>)}</div></section>
      {finished && <section className="border border-[#DDEBDD] bg-[#F5FBF5] p-4 text-sm"><strong>导入结果</strong><p className="mt-1 text-[#636366]">新增 {preview.batch.imported_rows} 条，更新 {preview.batch.updated_rows} 条，跳过 {preview.batch.skipped_rows} 条，失败 {preview.batch.error_rows} 条。回滚只处理本批新增且尚未被引用的资料。</p></section>}
      <button type="button" onClick={() => reset()} className="ui-button ui-button--quiet"><RotateCcw size={15}/>换一个文件</button>
    </div>}
  </ViewportDialog>;
}

function Metric({ label, value, danger = false }: { label: string; value: string | number; danger?: boolean }) { return <div className="bg-white px-4 py-3"><span className="block text-xs text-[#8E8E93]">{label}</span><strong className={`mt-1 block text-lg ${danger ? "text-[#C93531]" : "text-[#202025]"}`}>{value}</strong></div>; }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
