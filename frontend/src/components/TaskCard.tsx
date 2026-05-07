"use client";

import type { TaskItem } from "@/lib/types";
import StatusBadge from "./StatusBadge";

interface Props {
  task: TaskItem;
  onClick: (task: TaskItem) => void;
  onDelete?: (task: TaskItem) => void;
}

export default function TaskCard({ task, onClick, onDelete }: Props) {
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

      {onDelete && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(task); }}
          className="px-3 rounded-xl bg-[#FFF0F0] text-[#FF3B30] border border-[#FFD1D1]
            font-medium text-sm transition-all duration-200 hover:bg-[#FF3B30] hover:text-white
            flex-shrink-0 opacity-0 group-hover:opacity-100"
        >
          删除
        </button>
      )}
    </div>
  );
}
