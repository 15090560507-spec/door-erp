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
  const [activeDownloads, setActiveDownloads] = useState<Set<number>>(() => new Set());
  const [downloadErrors, setDownloadErrors] = useState<Record<number, string>>({});

  const download = async (attachment: SalesOrderAttachment) => {
    setActiveDownloads((current) => new Set(current).add(attachment.id));
    setDownloadErrors((current) => {
      if (!(attachment.id in current)) return current;
      const next = { ...current };
      delete next[attachment.id];
      return next;
    });
    try {
      await downloadFileFromUrl(
        `/sales-orders/${orderId}/attachments/${attachment.id}/file`,
        attachment.original_name,
      );
    } catch (downloadError) {
      setDownloadErrors((current) => ({
        ...current,
        [attachment.id]: apiErrorMessage(downloadError, "附件下载失败"),
      }));
    } finally {
      setActiveDownloads((current) => {
        const next = new Set(current);
        next.delete(attachment.id);
        return next;
      });
    }
  };

  return (
    <section className="order-summary__section">
      <div className="order-summary__section-title">
        <div><h3>订单图纸附件</h3></div>
        <strong>{attachments.length} 张</strong>
      </div>
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
                        disabled={activeDownloads.has(item.id)}
                        onClick={() => void download(item)}
                      >
                        <Download size={14} />
                      </button>
                      {downloadErrors[item.id] && <small className="order-attachment-summary__error" role="alert">{downloadErrors[item.id]}</small>}
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
