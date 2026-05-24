"use client";

import { useRef, useState } from "react";
import { analyzeDrawing } from "@/lib/quoteApi";
import type { AnalysisResult } from "@/lib/quoteTypes";

interface Props {
  onApply: (result: AnalysisResult) => void;
}

export default function AiAnalysisPanel({ onApply }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [status, setStatus] = useState("");
  const [rawJson, setRawJson] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleAnalyze() {
    if (!file) {
      setStatus("请先选择 JPG 或 PNG 图纸");
      return;
    }

    setLoading(true);
    setStatus("正在上传图纸并调用 AI 识别...");
    setResult(null);
    setRawJson("");

    try {
      const data = await analyzeDrawing(file);
      if (!data?.analysis) {
        throw new Error("AI 返回结果缺少 analysis 字段");
      }
      setResult(data.analysis);
      setRawJson(JSON.stringify(data.analysis, null, 2));
      setStatus(`识别完成：${data.filename || file.name}`);
    } catch (err: unknown) {
      const error = err as { userMessage?: string; message?: string };
      setStatus(error?.userMessage || error?.message || "识别失败");
    } finally {
      setLoading(false);
    }
  }

  function handleApply() {
    if (result) onApply(result);
  }

  function handleClear() {
    setFile(null);
    setResult(null);
    setRawJson("");
    setStatus("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6 space-y-4">
      <div>
        <h2 className="text-[15px] font-semibold text-[#1C1C1E]">图纸识别</h2>
        <p className="text-[12px] text-[#8E8E93]">支持 JPG、JPEG、PNG</p>
      </div>

      <div className="flex gap-3 items-end">
        <label className="flex-1">
          <span className="text-[12px] font-medium text-[#8E8E93]">图纸文件</span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="w-full mt-1 text-[13px] file:mr-3 file:py-1.5 file:px-3 file:text-[12px] file:font-medium file:rounded-lg file:border-0 file:bg-[#F2F2F7] file:text-[#1C1C1E] hover:file:bg-[#E5E5EA]/60 file:transition-colors file:cursor-pointer"
          />
        </label>
        <button
          onClick={handleAnalyze}
          disabled={loading || !file}
          className="px-5 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 disabled:opacity-50 transition-colors whitespace-nowrap"
        >
          {loading ? "识别中..." : "上传并识别"}
        </button>
      </div>

      {status && (
        <p className={`text-[12px] ${status.includes("失败") ? "text-[#FF3B30]" : "text-[#34C759]"}`}>
          {status}
        </p>
      )}

      {result && (
        <>
          <div className="bg-[#F2F2F7] rounded-xl p-4 text-[13px] space-y-1">
            <div>
              <span className="text-[#8E8E93]">客户：</span>
              <span className="text-[#1C1C1E] font-medium">{result.customerName || "未识别"}</span>
              <span className="mx-2 text-[#E5E5EA]">|</span>
              <span className="text-[#8E8E93]">项目：</span>
              <span className="text-[#1C1C1E] font-medium">{result.projectName || "未识别"}</span>
            </div>
            <div>
              <span className="text-[#8E8E93]">尺寸：</span>
              <span className="text-[#1C1C1E] font-medium">
                {result.outerWidth || "-"} x {result.outerHeight || "-"}
              </span>
              <span className="mx-2 text-[#E5E5EA]">|</span>
              <span className="text-[#8E8E93]">开启：</span>
              <span className="text-[#1C1C1E] font-medium">{result.openDirection || "未识别"}</span>
              <span className="mx-2 text-[#E5E5EA]">|</span>
              <span className="text-[#8E8E93]">明细：</span>
              <span className="text-[#1C1C1E] font-medium">{result.items?.length || 0} 条</span>
            </div>
            {result.accessories?.length > 0 && (
              <div>
                <span className="text-[#8E8E93]">配件：</span>
                <span className="text-[#1C1C1E] font-medium">{result.accessories.join("、")}</span>
              </div>
            )}
          </div>

          {rawJson && (
            <details className="text-[11px]">
              <summary className="text-[#8E8E93] cursor-pointer hover:text-[#1C1C1E] transition-colors">
                JSON 原始输出
              </summary>
              <pre className="mt-2 p-3 bg-[#F2F2F7] rounded-lg overflow-x-auto text-[#1C1C1E] text-[11px] leading-relaxed">
                {rawJson}
              </pre>
            </details>
          )}

          <div className="flex gap-2">
            <button
              onClick={handleApply}
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white hover:bg-[#007AFF]/90 transition-colors"
            >
              应用识别结果
            </button>
            <button
              onClick={handleClear}
              className="px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#1C1C1E] hover:bg-[#E5E5EA]/60 transition-colors"
            >
              清除
            </button>
          </div>
        </>
      )}

      {!result && !loading && (
        <p className="text-[13px] text-[#8E8E93]">
          上传图纸后，AI 会尝试识别客户名称、项目名称、外围尺寸和配件。
        </p>
      )}
    </div>
  );
}
