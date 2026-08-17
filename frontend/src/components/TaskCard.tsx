"use client";

import type { TaskItem } from "@/lib/types";
import StatusBadge from "./StatusBadge";

interface Props {
  task: TaskItem;
  onClick: (task: TaskItem) => void;
  onDelete?: (task: TaskItem) => void;
  onToggleQuoteStatus?: (task: TaskItem) => void;
  onToggleConfirmStatus?: (task: TaskItem) => void;
}

export default function TaskCard({
  task,
  onClick,
  onDelete,
  onToggleQuoteStatus,
  onToggleConfirmStatus,
}: Props) {
  const quoteStatus = task.quote_status || "未报价";
  const confirmStatus = task.confirm_status || "未确认";
  const quoted = quoteStatus === "已报价";
  const confirmed = confirmStatus === "已确认";

  return (
    <div className="flex items-stretch gap-2 mb-2 animate-fade-in group">
      <button
        onClick={() => onClick(task)}
        className="flex-1 text-left bg-white border border-[#E5E5EA] rounded-xl px-5 py-3.5
          shadow-sm hover:shadow-md hover:border-[#007AFF]/30 hover:-translate-y-0.5
          active:scale-[0.98] transition-all duration-200"
      >
        <div className="flex items-center gap-3">
          <span className="text-[15px] font-semibold text-[#1C1C1E] truncate">
            {task.customer}
          </span>
          <span className="text-[13px] text-[#8E8E93] truncate">- {task.project}</span>
          <StatusBadge status={task.status} />
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[#8E8E93] mt-1.5">
          <span className="bg-[#F2F2F7] px-2 py-0.5 rounded font-medium">{task.door_type}</span>
          {task.size && <span>{task.size}</span>}
          <span className="ml-auto">{task.date}</span>
        </div>
      </button>

      {(onToggleQuoteStatus || onToggleConfirmStatus) && (
        <div className="flex flex-col justify-center gap-1 flex-shrink-0 px-0.5">
          {onToggleQuoteStatus && (
            <button
              onClick={(e) => { e.stopPropagation(); onToggleQuoteStatus(task); }}
              title={`点击切换为${quoted ? "未报价" : "已报价"}`}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold border transition-all duration-200 ${
                quoted
                  ? "bg-[#E5F9E5] text-[#248A3D] border-[#9BD9A8] hover:bg-[#D3F3D3]"
                  : "bg-[#FFF8E5] text-[#B25E00] border-[#F2D38B] hover:bg-[#FFF0C7]"
              }`}
            >
              {quoteStatus}
            </button>
          )}
          {onToggleConfirmStatus && (
            <button
              onClick={(e) => { e.stopPropagation(); onToggleConfirmStatus(task); }}
              title={`点击切换为${confirmed ? "未确认" : "已确认"}`}
              className={`px-2.5 py-1 rounded-md text-xs font-semibold border transition-all duration-200 ${
                confirmed
                  ? "bg-[#E5F0FF] text-[#007AFF] border-[#A9CDF7] hover:bg-[#D8E9FF]"
                  : "bg-[#F2F2F7] text-[#636366] border-[#D9D9DE] hover:bg-[#E9E9ED]"
              }`}
            >
              {confirmStatus}
            </button>
          )}
        </div>
      )}

      {onDelete && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(task); }}
          className="px-3 rounded-xl bg-[#FFF0F0] text-[#FF3B30] border border-[#FFD1D1]
            font-medium text-sm transition-all duration-200 hover:bg-[#FF3B30] hover:text-white
            flex-shrink-0"
        >
          删除
        </button>
      )}
    </div>
  );
}
