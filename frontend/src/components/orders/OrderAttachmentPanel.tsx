import { ImagePlus, Trash2 } from "lucide-react";
import type { DragEvent } from "react";
import type { SalesOrderAttachment } from "@/lib/salesOrderTypes";

const categories: Array<{ key: SalesOrderAttachment["category"]; label: string }> = [
  { key: "door_drawing", label: "门类图纸" },
  { key: "customer_signed", label: "客户签字图纸" },
  { key: "quote_signed", label: "报价单签字图纸" },
  { key: "split_drawing", label: "拆分图纸" },
];

export default function OrderAttachmentPanel({ attachments, disabled, saved, onUpload, onDelete }: {
  attachments: SalesOrderAttachment[];
  disabled: boolean;
  saved: boolean;
  onUpload: (category: SalesOrderAttachment["category"], files: File[]) => void;
  onDelete: (attachment: SalesOrderAttachment) => void;
}) {
  const accept = (category: SalesOrderAttachment["category"], list: FileList | null) => {
    const files = Array.from(list || []).filter((file) => file.type.startsWith("image/"));
    if (files.length) onUpload(category, files);
  };
  const drop = (event: DragEvent<HTMLLabelElement>, category: SalesOrderAttachment["category"]) => {
    event.preventDefault();
    if (!disabled && saved) accept(category, event.dataTransfer.files);
  };
  return <section className="order-editor__section">
    <div className="order-editor__section-title"><div><h3>订单图纸附件</h3><p>每类可上传多张图片，也可直接拖入；当前均为非必填。</p></div></div>
    {!saved && <p className="order-attachments__hint">请先保存订单草稿，再上传图纸附件。</p>}
    <div className="order-attachments">
      {categories.map(({ key, label }) => {
        const items = attachments.filter((item) => item.category === key);
        return <div className="order-attachments__group" key={key}>
          <div className="order-attachments__heading"><strong>{label}</strong><span>{items.length} 张</span></div>
          <label className={`order-attachments__drop${disabled || !saved ? " is-disabled" : ""}`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => drop(event, key)}>
            <ImagePlus size={20} /><span>拖入图片或点击选择</span>
            <input hidden type="file" accept="image/*" multiple disabled={disabled || !saved} onChange={(event) => { accept(key, event.target.files); event.currentTarget.value = ""; }} />
          </label>
          <div className="order-attachments__files">{items.map((item) => <div key={item.id}><span title={item.original_name}>{item.original_name}</span>{!disabled && <button type="button" title="删除附件" aria-label={`删除 ${item.original_name}`} onClick={() => onDelete(item)}><Trash2 size={14} /></button>}</div>)}</div>
        </div>;
      })}
    </div>
  </section>;
}
