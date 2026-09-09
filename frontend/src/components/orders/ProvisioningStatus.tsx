import { AlertCircle, CheckCircle2, LoaderCircle, RefreshCw } from "lucide-react";
import type { SalesOrder } from "@/lib/salesOrderTypes";

export default function ProvisioningStatus({ order, busy, onRetry }: { order: SalesOrder; busy: boolean; onRetry: () => void }) {
  const status = order.provisioning_status || "not_started";
  if (order.status === "draft" || status === "not_started") return null;
  if (status === "ready") {
    return <div className="provisioning-status provisioning-status--ready" role="status"><CheckCircle2 size={19} aria-hidden="true" /><div><strong>履约资料已就绪</strong><p>已生成独立门樘生产编号和基础 BOM{order.fulfillment_order_id ? ` · 履约单 #${order.fulfillment_order_id}` : ""}</p></div></div>;
  }
  if (status === "failed") {
    return <div className="provisioning-status provisioning-status--failed" role="alert"><AlertCircle size={19} aria-hidden="true" /><div><strong>门樘与 BOM 生成失败</strong><p>{order.provisioning_error || "服务未返回具体原因，请重试后查看。"}</p></div><button type="button" className="ui-button ui-button--danger" disabled={busy} onClick={onRetry}><RefreshCw size={15} />重新生成</button></div>;
  }
  return <div className="provisioning-status provisioning-status--working" role="status" aria-live="polite"><LoaderCircle className="animate-spin" size={19} aria-hidden="true" /><div><strong>正在生成履约资料</strong><p>系统正在创建门樘生产编号与基础 BOM，请稍候。</p></div></div>;
}
