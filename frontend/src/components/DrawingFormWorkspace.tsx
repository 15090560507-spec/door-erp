"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import type { DoorFormData } from "@/lib/types";
import { apiErrorMessage, generateCadPreview } from "@/lib/api";
import { LatestPreviewQueue, previewFingerprint, previewReadiness } from "@/lib/liveCadPreview";
import CadPreviewPanel from "./CadPreviewPanel";

export default function DrawingFormWorkspace({ data, children }: { data: DoorFormData; children: ReactNode }) {
  const [automatic, setAutomatic] = useState(false);
  const [svg, setSvg] = useState<string | null>(null);
  const [renderedKey, setRenderedKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const queue = useRef<LatestPreviewQueue<DoorFormData> | null>(null);
  const latest = useRef(data);
  const key = useMemo(() => previewFingerprint(data), [data]);
  const readiness = previewReadiness(data);
  useEffect(() => {
    const worker = new LatestPreviewQueue(generateCadPreview, {
      success: (value, fingerprint) => { setSvg(value); setRenderedKey(fingerprint); setError(""); },
      error: value => setError(apiErrorMessage(value, "预览更新失败，请重试")),
      busy: setBusy,
    });
    queue.current = worker;
    return () => { worker.dispose(); queue.current = null; };
  }, []);
  useEffect(() => { latest.current = data; }, [data]);
  useEffect(() => {
    const worker = queue.current;
    if (!worker) return;
    worker.setDesired(key);
    worker.cancelPending();
    if (!automatic || readiness) return;
    const timer = window.setTimeout(() => worker.enqueue(key, latest.current), 1500);
    return () => window.clearTimeout(timer);
  }, [key, automatic, readiness]);
  const refresh = () => {
    if (readiness) return;
    queue.current?.setDesired(key);
    queue.current?.enqueue(key, data);
  };
  return (
    <div className="drawing-form-workspace">
      <div className="min-w-0">{children}</div>
      <aside data-live-cad-preview className="drawing-preview-dock">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-[#242429]">图纸小窗</h4>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-[#62626B]">
            自动预览
            <input type="checkbox" role="switch" aria-label="自动预览" checked={automatic}
              onChange={event => setAutomatic(event.target.checked)} className="h-4 w-4 accent-[#007AFF]" />
          </label>
        </div>
        <div className="my-3 flex items-center justify-between gap-2">
          <span role="status" className="text-xs text-[#777780]">{busy ? "正在更新..." : readiness || (svg && renderedKey !== key ? "参数已修改，待刷新" : automatic ? "自动预览已开启" : "自动预览已关闭")}</span>
          <button type="button" onClick={refresh} disabled={busy || Boolean(readiness)} title="刷新小窗" aria-label="刷新小窗"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[#D1D5DB] text-[#636366] hover:text-[#007AFF] disabled:opacity-40"><RefreshCw size={15} className={busy ? "animate-spin" : ""} /></button>
        </div>
        {error && <p role="alert" className="mb-3 text-xs text-[#C93531]">{error}</p>}
        {svg ? <CadPreviewPanel svg={svg} loading={false} embedded />
          : <div className="flex min-h-44 items-center justify-center rounded-md border border-[#E2E2E8] bg-[#F8FAFC] text-xs text-[#777780]">{busy ? "正在生成预览..." : "暂无预览"}</div>}
      </aside>
    </div>
  );
}
