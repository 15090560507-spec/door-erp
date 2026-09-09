import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
};

export default function EmptyState({ title, description, icon, action, compact = false }: EmptyStateProps) {
  return (
    <div className={`workspace-empty${compact ? " workspace-empty--compact" : ""}`} role="status">
      <span className="workspace-empty__icon" aria-hidden="true">{icon || <Inbox size={21} strokeWidth={1.7} />}</span>
      <strong>{title}</strong>
      {description && <p>{description}</p>}
      {action && <div className="workspace-empty__action">{action}</div>}
    </div>
  );
}
