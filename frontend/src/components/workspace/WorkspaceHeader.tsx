import type { ReactNode } from "react";

type WorkspaceHeaderProps = {
  title: string;
  description?: string;
  context?: ReactNode;
  actions?: ReactNode;
};

export default function WorkspaceHeader({ title, description, context, actions }: WorkspaceHeaderProps) {
  return (
    <header className="workspace-header">
      <div className="workspace-header__copy">
        {context && <div className="workspace-header__context">{context}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="workspace-header__actions">{actions}</div>}
    </header>
  );
}
