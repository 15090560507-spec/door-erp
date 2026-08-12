"use client";

import { downloadProductionFile, openProductionPrint } from "@/lib/productionApi";

export default function ProductionDocumentActions({
  excelPath,
  printPath,
  filename,
  disabled = false,
  notify,
}: {
  excelPath: string;
  printPath: string;
  filename: string;
  disabled?: boolean;
  notify: (message: string, error?: boolean) => void;
}) {
  const run = async (action: () => Promise<void>, success: string) => {
    try { await action(); notify(success); }
    catch (error) { notify(apiMessage(error, '单据输出失败'), true); }
  };
  return <div className="flex items-center gap-2">
    <button disabled={disabled} onClick={() => void run(() => downloadProductionFile(excelPath, `${filename}.xlsx`), 'Excel 已导出')} className="h-8 border border-[#C7C7CC] bg-white px-3 text-xs disabled:opacity-40">Excel</button>
    <button disabled={disabled} onClick={() => void run(() => openProductionPrint(printPath), '打印页面已打开')} className="h-8 border border-[#C7C7CC] bg-white px-3 text-xs disabled:opacity-40">打印 / PDF</button>
  </div>;
}

function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
