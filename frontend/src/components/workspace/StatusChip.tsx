import type { ReactNode } from "react";

export type StatusTone = "neutral" | "blue" | "green" | "amber" | "red" | "violet";

const inferredTone: Record<string, StatusTone> = {
  "已完成": "green", "已确认": "green", "已发布": "green", "已匹配": "green", "可执行": "green",
  "进行中": "blue", "履约中": "blue", "已排单": "blue",
  "待处理": "amber", "待确认": "amber", "待物料": "amber", "待前序": "amber", "待质检": "violet",
  "异常": "red", "不合格": "red", "缺料": "red", "已逾期": "red",
};

export default function StatusChip({ children, tone, dot = true }: { children: ReactNode; tone?: StatusTone; dot?: boolean }) {
  const text = typeof children === "string" ? children : "";
  const resolvedTone = tone || inferredTone[text] || "neutral";
  return (
    <span className={`status-chip status-chip--${resolvedTone}`}>
      {dot && <i aria-hidden="true" />}
      {children}
    </span>
  );
}
