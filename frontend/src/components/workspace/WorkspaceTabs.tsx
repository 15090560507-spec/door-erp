import type { ReactNode } from "react";

export type WorkspaceTabItem<T extends string> = {
  key: T;
  label: ReactNode;
};

export default function WorkspaceTabs<T extends string>({
  items,
  value,
  onChange,
  ariaLabel = "工作台视图",
}: {
  items: readonly WorkspaceTabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
}) {
  return (
    <nav className="workspace-tabs" aria-label={ariaLabel}>
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className={`workspace-tabs__item${value === item.key ? " is-active" : ""}`}
          aria-current={value === item.key ? "page" : undefined}
          onClick={() => onChange(item.key)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
