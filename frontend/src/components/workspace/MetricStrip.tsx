import type { CSSProperties, ReactNode } from "react";

export type MetricTone = "neutral" | "blue" | "green" | "amber" | "red" | "violet";

export type MetricItem = {
  key: string;
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  icon?: ReactNode;
  tone?: MetricTone;
  active?: boolean;
  onClick?: () => void;
};

export default function MetricStrip({ items, ariaLabel = "业务指标" }: { items: MetricItem[]; ariaLabel?: string }) {
  return (
    <section className="metric-strip" aria-label={ariaLabel} style={{ "--metric-count": Math.min(items.length, 6) } as CSSProperties}>
      {items.map((item) => {
        const content = (
          <>
            <span className="metric-strip__top">
              <span className="metric-strip__label">{item.label}</span>
              {item.icon && <span className="metric-strip__icon" aria-hidden="true">{item.icon}</span>}
            </span>
            <strong className="metric-strip__value">{item.value}</strong>
            {item.detail && <span className="metric-strip__detail">{item.detail}</span>}
          </>
        );
        const className = `metric-strip__item metric-strip__item--${item.tone || "neutral"}${item.active ? " is-active" : ""}`;
        return item.onClick ? (
          <button key={item.key} type="button" className={className} onClick={item.onClick}>{content}</button>
        ) : (
          <div key={item.key} className={className}>{content}</div>
        );
      })}
    </section>
  );
}
