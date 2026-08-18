"use client";

import { useCallback, useEffect, useState } from "react";
import TopNav from "@/components/TopNav";
import { useAuth } from "@/hooks/useAuth";
import {
  deleteLayeredRecord,
  generateLayeredRender,
  getTasks,
  listLayeredRecords,
} from "@/lib/api";
import type { LayeredRenderRecord, TaskItem } from "@/lib/types";

function apiMessage(error: unknown, fallback: string) {
  return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback;
}

export default function LayeredRenderPage() {
  const { setModule } = useAuth();
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [records, setRecords] = useState<LayeredRenderRecord[]>([]);
  const [taskId, setTaskId] = useState("");
  const [faces, setFaces] = useState<"both" | "front" | "back">("both");
  const [dpi, setDpi] = useState(300);
  const [targetLongEdge, setTargetLongEdge] = useState(4000);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ title: string; message: string; error: boolean } | null>(null);
  const [active, setActive] = useState<LayeredRenderRecord | null>(null);
  const [tab, setTab] = useState<"complete" | "front" | "back">("complete");

  const notify = useCallback((message: string, error = false) => setNotice({ title: error ? "生成失败" : "完成", message, error }), []);

  useEffect(() => { setModule("分层效果图"); }, [setModule]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        const [taskRes, recordRes] = await Promise.all([getTasks({ limit: 50 }), listLayeredRecords(20)]);
        if (cancelled) return;
        setTasks(taskRes.tasks || []);
        setRecords(recordRes.records || []);
      } catch (error) {
        if (!cancelled) notify(apiMessage(error, "数据加载失败"), true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void run();
    return () => { cancelled = true; };
  }, [notify]);

  const generate = async () => {
    if (!taskId) { notify("请先选择一个图纸任务", true); return; }
    setBusy(true);
    setActive(null);
    setTab("complete");
    try {
      const { record } = await generateLayeredRender({ taskId, faces, dpi, targetLongEdge });
      setActive(record);
      setRecords((prev) => [record, ...prev.filter((r) => r.id !== record.id)]);
      notify("分层效果图与 PSD 已生成，可预览并下载");
    } catch (error) {
      notify(apiMessage(error, "生成失败"), true);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await deleteLayeredRecord(id);
      setRecords((prev) => prev.filter((r) => r.id !== id));
      if (active?.id === id) setActive(null);
    } catch (error) {
      notify(apiMessage(error, "删除失败"), true);
    }
  };

  const previewUrl = active ? (tab === "front" ? active.files.front.url : tab === "back" ? active.files.back.url : active.files.complete.url) : "";

  return (
    <div className="min-h-screen bg-[#F5F5F7]">
      <TopNav />
      <main className="mx-auto max-w-7xl px-6 py-6">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h1 className="text-[20px] font-bold text-[#1C1C1E]">分层效果图</h1>
            <p className="mt-1 text-[13px] text-[#8E8E93]">基于已生成图纸的 CAD 结构，输出正面/反面分层效果图与 PSD（第一版规则化，默认平整材质）。</p>
          </div>
        </div>

        {notice && (
          <div className={`mb-4 rounded-lg border px-4 py-3 text-[13px] ${notice.error ? "border-[#FF3B30]/30 bg-[#FF3B30]/8 text-[#C9342D]" : "border-[#34C759]/30 bg-[#34C759]/8 text-[#248A3D]"}`}>
            {notice.message}
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {/* 左：任务与参数 */}
          <section className="rounded-xl border border-black/5 bg-white p-5 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
            <h2 className="mb-3 border-b border-[#F2F2F7] pb-2 text-[15px] font-semibold text-[#1C1C1E]">生成设置</h2>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-[13px] font-medium text-[#8E8E93]">图纸任务</label>
                <select value={taskId} onChange={(e) => setTaskId(e.target.value)} className="w-full rounded-md border border-[#C7C7CC] bg-[#FAFAFC] px-3 py-2 text-sm outline-none focus:border-[#007AFF]">
                  <option value="">请选择任务…</option>
                  {tasks.map((task) => (
                    <option key={task.id} value={task.id}>
                      {task.customer || "未命名"} · {task.project || task.door_type || ""} · {task.size || ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-[13px] font-medium text-[#8E8E93]">生成面</label>
                <div className="grid grid-cols-3 gap-2">
                  {([["both", "正反面"], ["front", "仅正面"], ["back", "仅反面"]] as const).map(([value, label]) => (
                    <button key={value} type="button" onClick={() => setFaces(value)}
                      className={`rounded-md border px-2 py-1.5 text-[13px] font-medium ${faces === value ? "border-[#007AFF] bg-[#007AFF]/8 text-[#007AFF]" : "border-[#D1D1D6] text-[#636366]"}`}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <details className="rounded-md border border-[#E5E5EA] p-2">
                <summary className="cursor-pointer text-[13px] font-medium text-[#8E8E93]">高级参数</summary>
                <div className="mt-2 grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-[12px] text-[#8E8E93]">分辨率 DPI</label>
                    <input type="number" value={dpi} onChange={(e) => setDpi(Number(e.target.value) || 300)} className="w-full rounded-md border border-[#C7C7CC] px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-[12px] text-[#8E8E93]">长边像素</label>
                    <input type="number" value={targetLongEdge} onChange={(e) => setTargetLongEdge(Number(e.target.value) || 4000)} className="w-full rounded-md border border-[#C7C7CC] px-3 py-2 text-sm" />
                  </div>
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-[#8E8E93]">DPI 写入 PSD 分辨率元数据；实际像素由“长边像素”控制（mm 1:1 的 300 DPI 会超出内存）。</p>
              </details>

              <button type="button" onClick={generate} disabled={busy || !taskId}
                className="w-full rounded-lg bg-[#007AFF] py-2.5 text-[14px] font-medium text-white disabled:opacity-50">
                {busy ? "生成中…" : "生成分层效果图"}
              </button>
            </div>
          </section>

          {/* 中：预览 */}
          <section className="rounded-xl border border-black/5 bg-white p-5 shadow-[0_4px_20px_rgba(0,0,0,0.03)] lg:col-span-2">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-[#F2F2F7] pb-2">
              <h2 className="text-[15px] font-semibold text-[#1C1C1E]">预览与下载</h2>
              {active && (
                <div className="flex flex-wrap gap-2">
                  <a href={active.files.psd.url} download={active.files.psd.originalName} className="rounded-md bg-[#1C1C1E] px-3 py-1.5 text-[12px] font-medium text-white">下载 PSD</a>
                  <a href={active.files.complete.url} download={active.files.complete.originalName} className="rounded-md border border-[#007AFF]/40 bg-[#007AFF]/5 px-3 py-1.5 text-[12px] font-medium text-[#007AFF]">完整订货单</a>
                  <a href={active.files.front.url} download={active.files.front.originalName} className="rounded-md border border-[#007AFF]/40 bg-[#007AFF]/5 px-3 py-1.5 text-[12px] font-medium text-[#007AFF]">正面效果图</a>
                  <a href={active.files.back.url} download={active.files.back.originalName} className="rounded-md border border-[#007AFF]/40 bg-[#007AFF]/5 px-3 py-1.5 text-[12px] font-medium text-[#007AFF]">反面效果图</a>
                </div>
              )}
            </div>

            {!active ? (
              <div className="flex min-h-[320px] items-center justify-center text-[13px] text-[#8E8E93]">
                {loading ? "加载中…" : "选择任务并点击“生成分层效果图”后，预览会显示在这里"}
              </div>
            ) : (
              <>
                <div className="mb-3 grid grid-cols-3 gap-2">
                  {([["complete", "完整订货单"], ["front", "正面"], ["back", "反面"]] as const).map(([value, label]) => (
                    <button key={value} type="button" onClick={() => setTab(value)}
                      className={`rounded-md px-2 py-1.5 text-[13px] font-medium ${tab === value ? "bg-[#1C1C1E] text-white" : "bg-[#F2F2F7] text-[#636366]"}`}>
                      {label}
                    </button>
                  ))}
                </div>
                <div className="flex max-h-[560px] items-center justify-center overflow-hidden rounded-lg border border-[#E5E5EA] bg-[#FAFAFC]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={previewUrl} alt="预览" className="max-h-[560px] w-full object-contain" />
                </div>
              </>
            )}
          </section>
        </div>

        {/* 历史记录 */}
        <section className="mt-5 rounded-xl border border-black/5 bg-white p-5 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
          <h2 className="mb-3 border-b border-[#F2F2F7] pb-2 text-[15px] font-semibold text-[#1C1C1E]">生成历史</h2>
          {records.length === 0 ? (
            <p className="text-[13px] text-[#8E8E93]">暂无生成记录</p>
          ) : (
            <div className="divide-y divide-[#F2F2F7]">
              {records.map((record) => (
                <div key={record.id} className="flex flex-wrap items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-medium text-[#1C1C1E]">{record.customer} · {record.canvasSize?.[0]}×{record.canvasSize?.[1]}px</div>
                    <div className="mt-0.5 text-[11px] text-[#8E8E93]">{record.createdAt} · {record.faces === "both" ? "正反面" : record.faces === "front" ? "正面" : "反面"}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <a href={record.files.psd.url} download={record.files.psd.originalName} className="rounded-md bg-[#1C1C1E] px-2.5 py-1 text-[11px] text-white">PSD</a>
                    <a href={record.files.complete.url} download={record.files.complete.originalName} className="rounded-md border border-[#D1D1D6] px-2.5 py-1 text-[11px] text-[#1C1C1E]">完整</a>
                    <a href={record.files.front.url} download={record.files.front.originalName} className="rounded-md border border-[#D1D1D6] px-2.5 py-1 text-[11px] text-[#1C1C1E]">正面</a>
                    <a href={record.files.back.url} download={record.files.back.originalName} className="rounded-md border border-[#D1D1D6] px-2.5 py-1 text-[11px] text-[#1C1C1E]">反面</a>
                    <button type="button" onClick={() => setActive(record)} className="rounded-md border border-[#007AFF]/40 px-2.5 py-1 text-[11px] text-[#007AFF]">查看</button>
                    <button type="button" onClick={() => remove(record.id)} className="rounded-md border border-[#FF3B30]/40 px-2.5 py-1 text-[11px] text-[#FF3B30]">删除</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
