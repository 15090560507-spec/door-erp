"use client";

import ProductionReleaseButton from "./ProductionReleaseButton";
import type { PendingProductionTask } from "@/lib/productionTypes";

export default function PendingReleaseList({
  tasks,
  canRelease,
  onReleased,
}: {
  tasks: PendingProductionTask[];
  canRelease: boolean;
  onReleased: () => void;
}) {
  return <section className="border border-[#D6D6DB] bg-white">
    <header className="flex items-center gap-3 border-b border-[#E5E5EA] px-5 py-4">
      <div><h2 className="font-semibold">待下达生产</h2><p className="mt-1 text-xs text-[#8E8E93]">终审已通过，尚未形成正式生产订单。</p></div>
      <span className="ml-auto bg-[#FFF4D6] px-2.5 py-1 text-xs font-semibold text-[#9A6700]">{tasks.length} 项</span>
    </header>
    <div className="overflow-x-auto">
      <table className="min-w-[980px] w-full table-fixed text-sm">
        <colgroup><col className="w-44" /><col className="w-44" /><col className="w-28" /><col className="w-36" /><col className="w-28" /><col className="w-40" /><col className="w-28" /><col className="w-28" /></colgroup>
        <thead className="bg-[#FAFAFC] text-left text-xs text-[#636366]"><tr>{['订货单位', '项目', '门型', '尺寸', '开向', '终审时间', '状态', '操作'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-3 py-3 font-medium">{label}</th>)}</tr></thead>
        <tbody>{tasks.map((task) => <tr key={`${task.task_id}-${task.source_revision}`} className="border-b border-[#F2F2F7]">
          <td className="truncate px-3 py-3 font-medium" title={task.customer}>{task.customer || '-'}</td>
          <td className="truncate px-3 py-3" title={task.project}>{task.project || '-'}</td>
          <td className="px-3 py-3">{task.door_type || '-'}</td>
          <td className="px-3 py-3">{task.width || '-'} × {task.height || '-'}</td>
          <td className="px-3 py-3">{task.opening || '-'}</td>
          <td className="px-3 py-3 text-xs text-[#636366]">{formatTime(task.approved_at)}</td>
          <td className="px-3 py-3"><span className="bg-[#FFF4D6] px-2 py-1 text-xs text-[#9A6700]">待下达</span></td>
          <td className="px-3 py-2">{canRelease ? <ProductionReleaseButton taskId={task.task_id} compact onReleased={onReleased} /> : <span className="text-xs text-[#8E8E93]">仅查看</span>}</td>
        </tr>)}</tbody>
      </table>
      {tasks.length === 0 && <div className="px-5 py-8 text-center text-sm text-[#8E8E93]">当前没有待下达的终审任务</div>}
    </div>
  </section>;
}

function formatTime(value: string) {
  if (!value) return '-';
  return value.replace('T', ' ').slice(0, 16);
}
