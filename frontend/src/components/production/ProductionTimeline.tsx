import type { ProductionTimelineItem } from "@/lib/productionTypes";

export default function ProductionTimeline({ items }: { items: ProductionTimelineItem[] }) {
  return <div className="border-l-2 border-[#D1D1D6] pl-5">
    {items.map((item) => <div key={item.id} className="relative border-b border-[#F2F2F7] py-4 first:pt-0">
      <span className="absolute -left-[27px] top-5 h-3 w-3 rounded-full border-2 border-white bg-[#007AFF] shadow" />
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"><strong className="text-sm">{item.title}</strong><span className="text-xs text-[#8E8E93]">{formatTime(item.created_at)}</span></div>
      <div className="mt-1 text-sm text-[#636366]">{item.detail || '无补充说明'}</div>
      <div className="mt-1 text-xs text-[#8E8E93]">操作人：{item.operator || '-'}</div>
    </div>)}
    {items.length === 0 && <div className="py-8 text-center text-sm text-[#8E8E93]">暂无操作记录</div>}
  </div>;
}

function formatTime(value: string) { return value ? value.replace('T', ' ').slice(0, 19) : '-'; }
