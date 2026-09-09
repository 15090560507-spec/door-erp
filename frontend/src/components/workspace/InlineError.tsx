import { AlertCircle, RotateCcw } from "lucide-react";

type InlineErrorProps = {
  title?: string;
  message: string;
  retryLabel?: string;
  onRetry?: () => void;
};

export default function InlineError({ title = "操作未完成", message, retryLabel = "重试", onRetry }: InlineErrorProps) {
  return (
    <div className="workspace-error" role="alert">
      <AlertCircle size={18} strokeWidth={1.8} aria-hidden="true" />
      <div><strong>{title}</strong><p>{message}</p></div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="workspace-error__retry">
          <RotateCcw size={14} aria-hidden="true" />{retryLabel}
        </button>
      )}
    </div>
  );
}
