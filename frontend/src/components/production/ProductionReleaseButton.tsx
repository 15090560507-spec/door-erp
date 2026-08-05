"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { releaseProductionOrder } from "@/lib/productionApi";

export default function ProductionReleaseButton({ taskId }: { taskId: string }) {
  const { user } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [dueDate, setDueDate] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  if (!user?.permissions?.includes("production.sales")) return null;

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
    } finally { setBusy(false); }
  };

  return <>
    <button onClick={() => setOpen(true)} className="w-full rounded-lg bg-[#248A3D] py-2.5 text-sm font-semibold text-white hover:opacity-90">下达生产订单</button>
    {open && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4" onClick={() => !busy && setOpen(false)}><div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}><h3 className="text-lg font-semibold">下达生产订单</h3><p className="mt-1 text-xs text-[#8E8E93]">将冻结终审图纸和当前参数。一张生产订单对应一樘门，报价不是必填项。</p>{message ? <><div className={`mt-5 rounded-lg px-4 py-3 text-sm ${message.error ? 'bg-[#FFF0F0] text-[#FF3B30]' : 'bg-[#E7F7EA] text-[#248A3D]'}`}>{message.text}</div><div className="mt-5 flex justify-end gap-2"><button onClick={() => setOpen(false)} className="h-9 bg-[#F2F2F7] px-4 text-sm">关闭</button>{!message.error && <button onClick={() => router.push('/production')} className="h-9 bg-[#007AFF] px-4 text-sm text-white">进入生产履约</button>}</div></> : <><div className="mt-5 space-y-4"><label className="block text-xs text-[#636366]"><span className="mb-1 block">要求交期</span><input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} className="h-10 w-full rounded-md border border-[#C7C7CC] px-3 text-sm" /></label><label className="block text-xs text-[#636366]"><span className="mb-1 block">销售说明</span><textarea rows={4} value={note} onChange={(event) => setNote(event.target.value)} placeholder="可填写包装、交付等生产说明" className="w-full resize-none rounded-md border border-[#C7C7CC] px-3 py-2 text-sm" /></label></div><div className="mt-5 flex justify-end gap-2"><button disabled={busy} onClick={() => setOpen(false)} className="h-9 bg-[#F2F2F7] px-4 text-sm">取消</button><button disabled={busy} onClick={submit} className="h-9 bg-[#248A3D] px-5 text-sm text-white disabled:opacity-50">{busy ? '正在下达...' : '确认下达'}</button></div></>}</div></div>}
  </>;
}
