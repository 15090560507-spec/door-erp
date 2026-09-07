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
    <div className="ui-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && onCancel) onCancel(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="notice-dialog-title" className="ui-dialog">
        <div className="ui-dialog__header">
          <h2 id="notice-dialog-title" className="ui-dialog__title">{title}</h2>
        </div>
        <div className="ui-dialog__body">
          <p className="whitespace-pre-wrap text-sm leading-6 text-[#5F5F68]">{message}</p>
        </div>
        <div className="ui-dialog__footer">
          {onCancel && <button type="button" onClick={onCancel} className="ui-button ui-button--secondary">{cancelLabel}</button>}
          <button type="button" onClick={onConfirm} className={`ui-button ${destructive ? "ui-button--danger" : "ui-button--primary"}`}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
