"use client";

import { Copy, Trash2 } from "lucide-react";
import type { TaskItem } from "@/lib/types";
import StatusBadge from "./StatusBadge";

interface Props {
  task: TaskItem;
  onClick: (task: TaskItem) => void;
  onDelete?: (task: TaskItem) => void;
  onCopy?: (task: TaskItem) => void;
  onToggleQuoteStatus?: (task: TaskItem) => void;
}

export default function TaskCard({
  task,
  onClick,
  onDelete,
  onCopy,
  onToggleQuoteStatus,
}: Props) {
  const quoteStatus = task.quote_status || "未报价";
  const confirmStatus = task.confirm_status || "未确认";
  const quoted = quoteStatus === "已报价";
  const isSimpleProduct = ["牌匾", "铝艺栅栏", "雨棚", "其他"].includes(task.params?.product_name);
  const productType = isSimpleProduct ? task.params.product_name : task.door_type;
  const productSize = isSimpleProduct
    ? `${task.params.dw || 0} x ${task.params.dh || 0}（${["雨棚", "牌匾", "其他"].includes(task.params.product_name) ? "宽×长" : "宽×高"}）`
    : task.size;

  return (
    <div className="task-list-row mb-2 flex items-stretch animate-fade-in group">
      <div
        role="button"
        tabIndex={0}
        onClick={() => onClick(task)}
        onKeyDown={(e) => { if (e.key === "Enter") onClick(task); }}
        className="task-list-row__main cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-semibold text-[#1C1C1E] truncate">
            {task.customer}
          </span>
          <span className="text-[13px] text-[#8E8E93] truncate">- {task.project}</span>
          <StatusBadge status={task.status} />
          {/* 未报价/已报价、未确认/已确认：时间上方的空白处，上下排列 */}
          {(onToggleQuoteStatus || confirmStatus) && (
            <div className="ml-auto flex flex-col items-end gap-0.5 flex-shrink-0 pl-2">
              {onToggleQuoteStatus && (
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleQuoteStatus(task); }}
                  title={`点击切换为${quoted ? "未报价" : "已报价"}`}
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition-all duration-200 ${
                    quoted
                      ? "bg-[#E5F9E5] text-[#248A3D] border-[#9BD9A8] hover:bg-[#D3F3D3]"
                      : "bg-[#F2F2F7] text-[#636366] border-[#D9D9DE] hover:bg-[#E9E9ED]"
                  }`}
                >
                  {quoteStatus}
                </button>
              )}
              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${confirmStatus === "已确认" ? "bg-[#E5F0FF] text-[#007AFF] border-[#A9CDF7]" : "bg-[#F2F2F7] text-[#636366] border-[#D9D9DE]"}`} title="由订单确认状态自动更新">{confirmStatus}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[#8E8E93] mt-1.5">
          <span className="bg-[#F2F2F7] px-2 py-0.5 rounded font-medium">{productType}</span>
          {productSize && <span>{productSize}</span>}
          <span className="ml-auto">{task.date}</span>
        </div>
      </div>

      {(onCopy || onDelete) && (
        <div className="task-list-row__actions">
          {onCopy && (
            <button
              onClick={(e) => { e.stopPropagation(); onCopy(task); }}
              className="task-list-row__action"
              title="复制表单"
              aria-label="复制表单"
            >
              <Copy size={16} />
            </button>
          )}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(task); }}
              className="task-list-row__action task-list-row__action--danger"
              title="删除表单"
              aria-label="删除表单"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
