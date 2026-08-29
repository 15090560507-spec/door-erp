interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel?: () => void;
}

export default function NoticeDialog({ title, message, confirmLabel = "知道了", cancelLabel = "取消", destructive = false, onConfirm, onCancel }: Props) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/35 px-4" onMouseDown={(event) => { if (event.target === event.currentTarget && onCancel) onCancel(); }}>
      <div role="dialog" aria-modal="true" className="w-full max-w-md border border-[#D1D1D6] bg-white p-5 shadow-2xl">
        <h2 className="text-base font-semibold text-[#1C1C1E]">{title}</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#636366]">{message}</p>
        <div className="mt-5 flex justify-end gap-2">
          {onCancel && <button type="button" onClick={onCancel} className="h-9 border border-[#D1D1D6] px-4 text-sm text-[#3C3C43]">{cancelLabel}</button>}
          <button type="button" onClick={onConfirm} className={`h-9 px-4 text-sm font-medium text-white ${destructive ? "bg-[#FF3B30]" : "bg-[#007AFF]"}`}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
