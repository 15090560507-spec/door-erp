"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteLayeredRecord,
  downloadFileFromUrl,
  generateLayeredRender,
  getTasks,
  listLayeredRecords,
} from "@/lib/api";
import {
  listRenderAssets,
  listRenderModelConfigs,
  type RenderAsset,
  type RenderModelConfig,
} from "@/lib/renderApi";
import type { LayeredRenderRecord, TaskItem } from "@/lib/types";

function apiMessage(error: unknown, fallback: string) {
  return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback;
}

/** 分层效果图（PSD）面板：CAD 管结构位置，可选接入效果渲染模型做 AI 材质处理。 */
export default function LayeredRenderPanel() {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [records, setRecords] = useState<LayeredRenderRecord[]>([]);
  const [configs, setConfigs] = useState<RenderModelConfig[]>([]);
  const [assets, setAssets] = useState<RenderAsset[]>([]);
  const [taskId, setTaskId] = useState("");
  const [faces, setFaces] = useState<"both" | "front" | "back">("both");
  const [modelConfigId, setModelConfigId] = useState("");
  const [referenceAssetIds, setReferenceAssetIds] = useState<string[]>([]);
  const [dpi, setDpi] = useState(300);
  const [targetLongEdge, setTargetLongEdge] = useState(2600);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const [active, setActive] = useState<LayeredRenderRecord | null>(null);
  const [tab, setTab] = useState<"complete" | "front" | "back">("complete");
  const [loaded, setLoaded] = useState(false);

  const notify = useCallback((message: string, error = false) => setNotice({ message, error }), []);

  const loadData = useCallback(async () => {
    const [taskRes, recordRes, configRes, assetRes] = await Promise.all([
      getTasks({ limit: 50 }),
      listLayeredRecords(20),
      listRenderModelConfigs(true).catch(() => []),
      listRenderAssets({ limit: 60 }).catch(() => []),
    ]);
    setTasks(taskRes.tasks || []);
    setRecords(recordRes.records || []);
    const enabled = (configRes || []).filter((item) => item.enabled);
    setConfigs(enabled);
    setModelConfigId((prev) => (prev || enabled[0]?.id || ""));
    setAssets(assetRes || []);
  }, []);

  useEffect(() => {
    if (!open || loaded) return;
    setLoaded(true);
    loadData().catch((error) => notify(apiMessage(error, "分层效果图数据加载失败"), true));
  }, [open, loaded, loadData, notify]);

  const generate = async () => {
    if (!taskId) { notify("请先选择一个图纸任务", true); return; }
    setBusy(true);
    setActive(null);
    setTab("complete");
    try {
      const { record } = await generateLayeredRender({
        taskId,
        faces,
        dpi,
        targetLongEdge,
        modelConfigId,
        referenceAssetIds,
      });
      setActive(record);
      setRecords((prev) => [record, ...prev.filter((r) => r.id !== record.id)]);
      if (record.materialMode === "ai") {
        notify("AI 材质处理完成，分层效果图与 PSD 已生成");
      } else if (record.materialNote) {
        notify(record.materialNote, true);
      } else {
        notify("分层效果图与 PSD 已生成（默认材质）");
      }
    } catch (error) {
      notify(apiMessage(error, "生成失败"), true);
    } finally {
      setBusy(false);
    }
  };

  const toggleAsset = (id: string) => {
    setReferenceAssetIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  };

  const download = async (file: { url: string; originalName: string }) => {
    try {
      await downloadFileFromUrl(file.url, file.originalName);
    } catch (error) {
      notify(apiMessage(error, "下载失败"), true);
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
  const assetsByCategory: Record<string, RenderAsset[]> = {};
  for (const asset of assets) {
    (assetsByCategory[asset.category || "其他"] ||= []).push(asset);
  }

  return (
    <section className="rounded-2xl border border-[#E5E5EA]/60 bg-white p-4">
      <button type="button" onClick={() => setOpen((value) => !value)} className="text-left">
        <h2 className="text-[15px] font-semibold text-[#1C1C1E]">{open ? "▼" : "▶"} 分层效果图（PSD）</h2>
        <p className="mt-1 text-[12px] text-[#8E8E93]">基于图纸任务的 CAD 结构生成正反面分层 PSD 与 JPG；可选接入上方模型配置做 AI 材质处理（CAD 管结构，AI 只上色/材质）。</p>
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          {notice && (
            <div className={`rounded-lg border px-3 py-2 text-[13px] ${notice.error ? "border-[#FF3B30]/30 bg-[#FF3B30]/8 text-[#C9342D]" : "border-[#34C759]/30 bg-[#34C759]/8 text-[#248A3D]"}`}>
              {notice.message}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[300px_1fr]">
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-[13px] font-medium text-[#8E8E93]">图纸任务</label>
                <select value={taskId} onChange={(e) => setTaskId(e.target.value)} className="w-full rounded-lg border border-[#E5E5EA] bg-[#FAFAFC] px-3 py-2 text-[13px] outline-none focus:border-[#007AFF]">
                  <option value="">请选择任务…</option>
                  {tasks.map((task) => (
                    <option key={task.id} value={task.id}>
                      {task.customer || "未命名"} · {task.project || task.door_type || ""} · {task.size || ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-[13px] font-medium text-[#8E8E93]">材质处理（AI 模型）</label>
                <select value={modelConfigId} onChange={(e) => setModelConfigId(e.target.value)} className="w-full rounded-lg border border-[#E5E5EA] bg-[#FAFAFC] px-3 py-2 text-[13px] outline-none focus:border-[#007AFF]">
                  <option value="">不使用 AI（默认平整材质）</option>
                  {configs.map((config) => (
                    <option key={config.id} value={config.id}>{config.name || config.model || config.id}</option>
                  ))}
                </select>
                {configs.length === 0 && <p className="mt-1 text-[11px] text-[#8E8E93]">尚未配置可用的 AI 模型，请在页面上方「模型配置」里添加。</p>}
              </div>

              <div>
                <label className="mb-1 block text-[13px] font-medium text-[#8E8E93]">参考素材（可多选，供 AI 提取颜色材质）</label>
                {assets.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-[#C7C7CC] px-3 py-2 text-[12px] text-[#8E8E93]">素材库暂无素材，可先在上方素材库上传。</p>
                ) : (
                  <div className="max-h-44 space-y-2 overflow-y-auto rounded-lg border border-[#E5E5EA] p-2">
                    {Object.entries(assetsByCategory).map(([categoryName, items]) => (
                      <div key={categoryName}>
                        <div className="mb-1 text-[11px] font-medium text-[#8E8E93]">{categoryName}</div>
                        <div className="flex flex-wrap gap-1.5">
                          {items.map((asset) => {
                            const selected = referenceAssetIds.includes(asset.id);
                            return (
                              <button
                                key={asset.id}
                                type="button"
                                onClick={() => toggleAsset(asset.id)}
                                className={`max-w-[180px] truncate rounded-full border px-2 py-0.5 text-[11px] ${selected ? "border-[#007AFF] bg-[#007AFF]/10 text-[#007AFF]" : "border-[#D1D1D6] bg-white text-[#3C3C43]"}`}
                              >
                                {asset.name || asset.id}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <label className="mb-1 block text-[13px] font-medium text-[#8E8E93]">生成面</label>
                <div className="grid grid-cols-3 gap-2">
                  {([["both", "正反面"], ["front", "仅正面"], ["back", "仅反面"]] as const).map(([value, label]) => (
                    <button key={value} type="button" onClick={() => setFaces(value)}
                      className={`rounded-lg border px-2 py-1.5 text-[12px] font-medium ${faces === value ? "border-[#007AFF] bg-[#007AFF]/8 text-[#007AFF]" : "border-[#D1D1D6] text-[#636366]"}`}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <details className="rounded-lg border border-[#E5E5EA] p-2">
                <summary className="cursor-pointer text-[12px] font-medium text-[#8E8E93]">高级参数</summary>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <label>
                    <span className="mb-1 block text-[11px] text-[#8E8E93]">分辨率 DPI</span>
                    <input type="number" value={dpi} onChange={(e) => setDpi(Number(e.target.value) || 300)} className="w-full rounded-lg border border-[#E5E5EA] px-2 py-1.5 text-[12px]" />
                  </label>
                  <label>
                    <span className="mb-1 block text-[11px] text-[#8E8E93]">长边像素</span>
                    <input type="number" value={targetLongEdge} onChange={(e) => setTargetLongEdge(Number(e.target.value) || 2600)} className="w-full rounded-lg border border-[#E5E5EA] px-2 py-1.5 text-[12px]" />
                  </label>
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-[#8E8E93]">DPI 写入 PSD 分辨率元数据；实际像素由“长边像素”控制（默认 2600）。数值越大 PSD 体积越大。</p>
              </details>

              <button type="button" onClick={generate} disabled={busy || !taskId}
                className="w-full rounded-lg bg-[#007AFF] py-2 text-[13px] font-medium text-white disabled:opacity-50">
                {busy ? (modelConfigId ? "AI 处理中，可能需要 1-2 分钟…" : "生成中…") : "生成分层效果图"}
              </button>
            </div>

            <div>
              {!active ? (
                <div className="flex min-h-[240px] items-center justify-center rounded-xl border border-dashed border-[#C7C7CC] bg-[#F2F2F7] text-[13px] text-[#8E8E93]">
                  选择任务并点击“生成分层效果图”后，预览会显示在这里
                </div>
              ) : (
                <>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <div className="grid flex-1 grid-cols-3 gap-2">
                      {([["complete", "完整订货单"], ["front", "正面"], ["back", "反面"]] as const).map(([value, label]) => (
                        <button key={value} type="button" onClick={() => setTab(value)}
                          className={`rounded-lg px-2 py-1.5 text-[12px] font-medium ${tab === value ? "bg-[#1C1C1E] text-white" : "bg-[#F2F2F7] text-[#636366]"}`}>
                          {label}
                        </button>
                      ))}
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${active.materialMode === "ai" ? "bg-[#34C759]/10 text-[#248A3D]" : "bg-[#F2F2F7] text-[#636366]"}`}>
                      {active.materialMode === "ai" ? `AI 材质 · ${active.modelConfig?.name || active.modelConfig?.model || ""}` : "默认材质"}
                    </span>
                    <button type="button" onClick={() => download(active.files.psd)} className="rounded-lg bg-[#1C1C1E] px-3 py-1.5 text-[12px] font-medium text-white">下载 PSD</button>
                    <button type="button" onClick={() => download(tab === "front" ? active.files.front : tab === "back" ? active.files.back : active.files.complete)} className="rounded-lg border border-[#007AFF]/40 bg-[#007AFF]/5 px-3 py-1.5 text-[12px] font-medium text-[#007AFF]">下载当前图</button>
                  </div>
                  {active.materialNote && <p className="mb-2 rounded-lg bg-[#FF3B30]/8 px-3 py-1.5 text-[12px] text-[#C9342D]">{active.materialNote}</p>}
                  <div className="flex max-h-[520px] items-center justify-center overflow-hidden rounded-xl border border-[#E5E5EA] bg-[#FAFAFC]">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={previewUrl} alt="分层效果图预览" className="max-h-[520px] w-full object-contain" />
                  </div>
                </>
              )}
            </div>
          </div>

          {records.length > 0 && (
            <div>
              <h3 className="mb-2 text-[13px] font-semibold text-[#1C1C1E]">生成历史</h3>
              <div className="divide-y divide-[#F2F2F7] rounded-xl border border-[#E5E5EA]">
                {records.map((record) => (
                  <div key={record.id} className="flex flex-wrap items-center gap-2 px-3 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[12px] font-medium text-[#1C1C1E]">
                        {record.customer} · {record.canvasSize?.[0]}×{record.canvasSize?.[1]}px
                        <span className={`ml-2 rounded-full px-1.5 text-[10px] ${record.materialMode === "ai" ? "bg-[#34C759]/10 text-[#248A3D]" : "bg-[#F2F2F7] text-[#636366]"}`}>
                          {record.materialMode === "ai" ? "AI材质" : "默认材质"}
                        </span>
                      </div>
                      <div className="mt-0.5 text-[11px] text-[#8E8E93]">{record.createdAt} · {record.faces === "both" ? "正反面" : record.faces === "front" ? "正面" : "反面"}</div>
                    </div>
                    <button type="button" onClick={() => download(record.files.psd)} className="rounded-md bg-[#1C1C1E] px-2 py-1 text-[11px] text-white">PSD</button>
                    <button type="button" onClick={() => download(record.files.complete)} className="rounded-md border border-[#D1D1D6] px-2 py-1 text-[11px]">完整</button>
                    <button type="button" onClick={() => download(record.files.front)} className="rounded-md border border-[#D1D1D6] px-2 py-1 text-[11px]">正面</button>
                    <button type="button" onClick={() => download(record.files.back)} className="rounded-md border border-[#D1D1D6] px-2 py-1 text-[11px]">反面</button>
                    <button type="button" onClick={() => setActive(record)} className="rounded-md border border-[#007AFF]/40 px-2 py-1 text-[11px] text-[#007AFF]">查看</button>
                    <button type="button" onClick={() => remove(record.id)} className="rounded-md border border-[#FF3B30]/40 px-2 py-1 text-[11px] text-[#FF3B30]">删除</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
