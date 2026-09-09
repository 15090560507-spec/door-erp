import type { CSSProperties, ReactNode } from "react";

type MasterDetailProps = {
  list: ReactNode;
  detail: ReactNode;
  listLabel?: string;
  detailLabel?: string;
  listWidth?: number;
  className?: string;
};

export default function MasterDetail({
  list,
  detail,
  listLabel = "列表",
  detailLabel = "详情",
  listWidth = 360,
  className = "",
}: MasterDetailProps) {
  return (
    <div
      className={`workspace-master-detail ${className}`.trim()}
      style={{ "--master-width": `${listWidth}px` } as CSSProperties}
    >
      <aside className="workspace-master-detail__master" aria-label={listLabel}>{list}</aside>
      <section className="workspace-master-detail__detail" aria-label={detailLabel}>{detail}</section>
    </div>
  );
}
