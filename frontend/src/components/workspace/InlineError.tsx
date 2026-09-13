import { AlertCircle, RotateCcw, X } from "lucide-react";

type InlineErrorProps = {
  title?: string;
  message: string;
  retryLabel?: string;
  onRetry?: () => void;
  dismissLabel?: string;
  onDismiss?: () => void;
};

export default function InlineError({
  title = "操作未完成",
  message,
  retryLabel = "重试",
  onRetry,
  dismissLabel = "关闭",
  onDismiss,
}: InlineErrorProps) {
  return (
    <div className="workspace-error" role="alert">
      <AlertCircle size={18} strokeWidth={1.8} aria-hidden="true" />
      <div><strong>{title}</strong><p>{message}</p></div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="workspace-error__retry">
          <RotateCcw size={14} aria-hidden="true" />{retryLabel}
        </button>
      )}
      {onDismiss && (
        <button type="button" onClick={onDismiss} className="workspace-error__retry">
          <X size={14} aria-hidden="true" />{dismissLabel}
        </button>
      )}
    </div>
  );
}
