"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { releaseProductionOrder } from "@/lib/productionApi";

export default function ProductionReleaseButton({
  taskId,
  compact = false,
  onReleased,
}: {
  taskId: string;
  compact?: boolean;
  onReleased?: () => void;
}) {
  const { user } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [dueDate, setDueDate] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  if (!user?.permissions?.includes("production.sales")) return null;

  const close = () => {
    const released = Boolean(message && !message.error);
    setOpen(false);
    setMessage(null);
    if (released) onReleased?.();
  };

  const submit = async () => {
    setBusy(true);
    try {
      const result = await releaseProductionOrder(taskId, {
        due_date: dueDate,
        sales_note: note,
        include_quote: false,
      });
      setMessage({ text: `${result.message}：${result.order.order_no}`, error: false });
    } catch (error) {
      setMessage({ text: (error as { userMessage?: string })?.userMessage || "下达生产失败", error: true });
    } finally {
      setBusy(false);
    }
  };

  return <>
    <button
      onClick={() => setOpen(true)}
      className={`${compact ? "h-8 px-3 text-xs" : "w-full py-2.5 text-sm"} bg-[#248A3D] font-semibold text-white hover:opacity-90`}
    >
      下达生产
    </button>
    {open && <div className="ui-dialog-backdrop" onClick={() => !busy && close()}>
      <div className="ui-dialog" onClick={(event) => event.stopPropagation()}>
        <div className="ui-dialog__header"><div><h3 className="ui-dialog__title">下达 ERPNext 生产订单</h3>
        <p className="ui-dialog__description">
          将冻结终审图纸和当前参数，并创建 ERPNext 草稿订单。一张生产订单对应一樘门，报价不是必填项；同步失败可在生产管理中重试。
        </p></div></div>
        <div className="ui-dialog__body">
        {message ? <>
          <div className={`px-4 py-3 text-sm ${message.error ? "bg-[#FFF0F0] text-[#FF3B30]" : "bg-[#E7F7EA] text-[#248A3D]"}`}>
            {message.text}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button onClick={close} className="ui-button ui-button--secondary">关闭</button>
            {!message.error && <button onClick={() => { onReleased?.(); router.push("/production"); }} className="ui-button ui-button--primary">查看生产管理</button>}
          </div>
        </> : <>
          <div className="mt-5 space-y-4">
            <label className="block text-xs text-[#636366]">
              <span className="mb-1 block">要求交期</span>
              <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} className="h-10 w-full rounded-md border border-[#C7C7CC] px-3 text-sm" />
            </label>
            <label className="block text-xs text-[#636366]">
              <span className="mb-1 block">销售说明</span>
              <textarea rows={4} value={note} onChange={(event) => setNote(event.target.value)} placeholder="可填写包装、交付等生产说明" className="w-full resize-none rounded-md border border-[#C7C7CC] px-3 py-2 text-sm" />
            </label>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button disabled={busy} onClick={close} className="ui-button ui-button--secondary">取消</button>
            <button disabled={busy} onClick={submit} className="ui-button ui-button--primary">{busy ? "正在下达..." : "确认下达"}</button>
          </div>
        </>}
        </div>
      </div>
    </div>}
  </>;
}
