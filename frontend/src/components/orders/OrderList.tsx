import { FileText } from "lucide-react";
import EmptyState from "@/components/workspace/EmptyState";
import LoadingPanel from "@/components/workspace/LoadingPanel";
import StatusChip, { type StatusTone } from "@/components/workspace/StatusChip";
import type { SalesOrderSummary } from "@/lib/salesOrderTypes";

export const salesOrderStatusLabel: Record<string, string> = {
  draft: "草稿",
  confirmed: "已确认",
  fulfilling: "履约中",
  completed: "已完成",
  cancelled: "已取消",
};

const statusTone: Record<string, StatusTone> = {
  draft: "blue", confirmed: "green", fulfilling: "blue", completed: "green", cancelled: "neutral",
};

export default function OrderList({ orders, selectedId, loading, disabled, onSelect, onCreate }: {
  orders: SalesOrderSummary[];
  selectedId?: number;
  loading: boolean;
  disabled?: boolean;
  onSelect: (orderId: number) => void;
  onCreate: () => void;
}) {
  if (loading) return <LoadingPanel rows={7} label="正在加载销售订单" />;
  if (!orders.length) {
    return <EmptyState title="暂无订单" description="可从已终审图纸和报价快速创建。" icon={<FileText size={21} />} action={<button type="button" className="ui-button ui-button--primary" onClick={onCreate}>新建订单</button>} />;
  }
  return (
    <div className="order-list">
      {orders.map((order) => (
        <button key={order.id} type="button" disabled={disabled} onClick={() => onSelect(order.id)} className={`order-list__item${selectedId === order.id ? " is-active" : ""}`}>
          <span className="order-list__heading"><strong>{order.order_no}</strong><StatusChip tone={statusTone[order.status]}>{salesOrderStatusLabel[order.status] || order.status}</StatusChip></span>
          <span className="order-list__customer">{order.customer_name}{order.project_name ? ` · ${order.project_name}` : ""}</span>
          <span className="order-list__product"><strong>{order.first_door_type || order.first_product_name || "未填写门型"}</strong><span>{Number(order.first_width || 0) > 0 ? `${order.first_width} × ${order.first_height} mm` : "尺寸待补充"}{order.line_count > 1 ? ` · 另有 ${order.line_count - 1} 项` : ""}</span></span>
          <span className="order-list__meta"><span>{order.door_count} 樘 · 交期 {order.delivery_date || "未设置"}</span><strong>¥{order.total_amount.toLocaleString()}</strong></span>
          {order.provisioning_status === "failed" && <span className="order-list__warning">门樘与 BOM 生成失败</span>}
        </button>
      ))}
    </div>
  );
}
