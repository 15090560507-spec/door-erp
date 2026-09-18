"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { apiErrorMessage, downloadFileFromUrl } from "@/lib/api";
import type { SalesOrderAttachment } from "@/lib/salesOrderTypes";

const categories: Array<{ key: SalesOrderAttachment["category"]; label: string }> = [
  { key: "door_drawing", label: "门类图纸" },
  { key: "customer_signed", label: "客户签字图纸" },
  { key: "quote_signed", label: "报价单签字图纸" },
  { key: "split_drawing", label: "拆分图纸" },
];

export default function OrderAttachmentSummary({ orderId, attachments }: {
  orderId: number;
  attachments: SalesOrderAttachment[];
}) {
  const [downloadingId, setDownloadingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const download = async (attachment: SalesOrderAttachment) => {
    setDownloadingId(attachment.id);
    setError("");
    try {
      await downloadFileFromUrl(
        `/sales-orders/${orderId}/attachments/${attachment.id}/file`,
        attachment.original_name,
      );
    } catch (downloadError) {
      setError(apiErrorMessage(downloadError, "附件下载失败"));
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <section className="order-summary__section">
      <div className="order-summary__section-title">
        <div><h3>订单图纸附件</h3></div>
        <strong>{attachments.length} 张</strong>
      </div>
      {error && <p className="order-attachment-summary__error" role="alert">{error}</p>}
      <div className="order-attachments order-attachments--summary">
        {categories.map(({ key, label }) => {
          const items = attachments.filter((item) => item.category === key);
          return (
            <div className="order-attachments__group" key={key}>
              <div className="order-attachments__heading"><strong>{label}</strong><span>{items.length} 张</span></div>
              {items.length ? (
                <div className="order-attachments__files">
                  {items.map((item) => (
                    <div key={item.id}>
                      <span title={item.original_name}>{item.original_name}</span>
                      <button
                        type="button"
                        title="下载附件"
                        aria-label={`下载 ${item.original_name}`}
                        disabled={downloadingId === item.id}
                        onClick={() => void download(item)}
                      >
                        <Download size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : <p className="order-attachment-summary__empty">暂无附件</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
