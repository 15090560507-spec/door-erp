import type { ReactNode } from "react";

type FilterBarProps = {
  children: ReactNode;
  actions?: ReactNode;
  summary?: ReactNode;
  className?: string;
};

export default function FilterBar({ children, actions, summary, className = "" }: FilterBarProps) {
  return (
    <section className={`workspace-filter ${className}`.trim()} aria-label="筛选条件">
      <div className="workspace-filter__fields">{children}</div>
      {summary && <div className="workspace-filter__summary">{summary}</div>}
      {actions && <div className="workspace-filter__actions">{actions}</div>}
    </section>
  );
}
