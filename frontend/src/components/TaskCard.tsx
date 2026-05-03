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
    <div className="flex items-stretch gap-1 mb-2">
      <button
        onClick={() => onClick(task)}
        className="flex-1 text-left bg-white border border-[#E5E5EA] rounded-[10px] px-5 py-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)] transition-all duration-200 hover:border-[#007AFF] hover:shadow-lg hover:-translate-y-0.5 active:scale-[0.98]"
      >
        <div className="flex items-center gap-3">
          <span className="text-[#1C1C1E] font-medium">📂 {task.customer} - {task.project}</span>
          <StatusBadge status={task.status} />
        </div>
        <div className="text-[13px] text-[#8E8E93] mt-1">
          门型：{task.door_type} | 洞口：{task.size} | {task.date}
        </div>
      </button>

      {onDelete && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(task); }}
          className="px-3 rounded-[10px] bg-[#FFF0F0] text-[#FF3B30] border border-[#FFD1D1] font-medium text-sm transition-all duration-200 hover:bg-[#FF3B30] hover:text-white flex-shrink-0"
        >
          🗑
        </button>
      )}
    </div>
  );
}
