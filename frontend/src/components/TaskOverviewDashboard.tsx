"use client";

import type { TaskOverviewData } from "@/lib/types";

interface Props {
  data: TaskOverviewData;
  activeStatus: string;
  onStatus: (status: string) => void;
  onQuery: (query: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  待绘制: "#636366",
  待初审: "#FF9F0A",
  待终审: "#BF6A02",
  待修改: "#FF3B30",
  已通过: "#34C759",
};

export default function TaskOverviewDashboard({ data, activeStatus, onStatus, onQuery }: Props) {
  const metrics = [
    { label: "全部图纸", value: data.total, status: "" },
    { label: "今日新增", value: data.today_created, status: "" },
    { label: "待绘制", value: data.status_counts["待绘制"] || 0, status: "待绘制" },
    { label: "待修改", value: data.status_counts["待修改"] || 0, status: "待修改" },
    { label: "已通过", value: data.status_counts["已通过"] || 0, status: "已通过" },
  ];
  const maxTrend = Math.max(1, ...data.trend.flatMap((item) => [item.created, item.approved]));
  const chartWidth = 700;
  const chartHeight = 180;
  const chartTop = 18;
  const chartBottom = 34;
  const plotHeight = chartHeight - chartTop - chartBottom;
  const slot = chartWidth / Math.max(data.trend.length, 1);

  return (
    <section className="mb-5 overflow-hidden rounded-lg border border-[#D9E7F5] bg-white shadow-sm">
      <div className="grid grid-cols-2 border-b border-[#E5E5EA] md:grid-cols-5">
        {metrics.map((metric) => {
          const active = Boolean(metric.status) && activeStatus === metric.status;
          return (
            <button
              key={metric.label}
              type="button"
              onClick={() => metric.status && onStatus(active ? "" : metric.status)}
              className={`min-h-[88px] border-b border-r border-[#E5E5EA] px-5 py-4 text-left transition-colors md:border-b-0 ${
                metric.status ? "hover:bg-[#F5FAFF]" : "cursor-default"
              } ${active ? "bg-[#EAF4FF]" : "bg-white"}`}
            >
              <div className="text-[12px] font-medium text-[#636366]">{metric.label}</div>
              <div className="mt-1 text-[28px] font-semibold tabular-nums text-[#1C1C1E]">{metric.value}</div>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
        <div className="border-b border-[#E5E5EA] p-5 xl:border-b-0 xl:border-r">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[15px] font-semibold text-[#1C1C1E]">近 14 天图纸流转</h3>
            <div className="flex gap-4 text-[11px] text-[#636366]">
              <span><i className="mr-1 inline-block h-2 w-2 bg-[#007AFF]" />新增</span>
              <span><i className="mr-1 inline-block h-2 w-2 bg-[#34C759]" />终审通过</span>
            </div>
          </div>
          <div className="aspect-[3.9/1] min-h-[190px] w-full">
            <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="h-full w-full" role="img" aria-label="近十四天新增和终审通过趋势">
              {[0, 0.5, 1].map((ratio) => {
                const y = chartTop + plotHeight * ratio;
                return <line key={ratio} x1="0" x2={chartWidth} y1={y} y2={y} stroke="#E5E5EA" strokeWidth="1" />;
              })}
              {data.trend.map((item, index) => {
                const x = index * slot + slot * 0.22;
                const createdHeight = (item.created / maxTrend) * plotHeight;
                const approvedHeight = (item.approved / maxTrend) * plotHeight;
                return (
                  <g key={item.date}>
                    <rect x={x} y={chartTop + plotHeight - createdHeight} width={Math.max(5, slot * 0.22)} height={createdHeight} fill="#007AFF" rx="1" />
                    <rect x={x + slot * 0.27} y={chartTop + plotHeight - approvedHeight} width={Math.max(5, slot * 0.22)} height={approvedHeight} fill="#34C759" rx="1" />
                    {(index % 2 === 0 || index === data.trend.length - 1) && (
                      <text x={index * slot + slot / 2} y={chartHeight - 10} textAnchor="middle" fontSize="10" fill="#8E8E93">{item.label}</text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        <div className="p-5">
          <h3 className="mb-4 text-[15px] font-semibold text-[#1C1C1E]">当前流程分布</h3>
          <div className="space-y-3">
            {Object.entries(STATUS_COLORS).map(([status, color]) => {
              const count = data.status_counts[status] || 0;
              const ratio = data.total ? Math.max(2, (count / data.total) * 100) : 0;
              return (
                <button key={status} type="button" onClick={() => onStatus(activeStatus === status ? "" : status)} className="block w-full text-left">
                  <div className="mb-1 flex items-center justify-between text-[12px]">
                    <span className="font-medium text-[#3A3A3C]">{status}</span>
                    <span className="tabular-nums text-[#636366]">{count}</span>
                  </div>
                  <div className="h-2 overflow-hidden bg-[#F2F2F7]">
                    <div className="h-full transition-[width]" style={{ width: `${ratio}%`, backgroundColor: color }} />
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 border-t border-[#E5E5EA] md:grid-cols-2">
        <Ranking title="客户图纸量" items={data.customers} onQuery={onQuery} />
        <Ranking title="门型分布" items={data.door_types} onQuery={onQuery} divider />
      </div>
    </section>
  );
}

function Ranking({ title, items, onQuery, divider = false }: {
  title: string;
  items: { name: string; count: number }[];
  onQuery: (query: string) => void;
  divider?: boolean;
}) {
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <div className={`p-5 ${divider ? "border-t border-[#E5E5EA] md:border-l md:border-t-0" : ""}`}>
      <h3 className="mb-3 text-[15px] font-semibold text-[#1C1C1E]">{title}</h3>
      {items.length === 0 ? (
        <div className="py-5 text-sm text-[#8E8E93]">暂无数据</div>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {items.map((item) => (
            <button key={item.name} type="button" onClick={() => onQuery(item.name)} className="group min-w-0 py-1 text-left">
              <div className="flex items-center gap-2 text-[12px]">
                <span className="min-w-0 flex-1 truncate text-[#3A3A3C] group-hover:text-[#007AFF]">{item.name}</span>
                <span className="tabular-nums text-[#8E8E93]">{item.count}</span>
              </div>
              <div className="mt-1 h-1.5 bg-[#F2F2F7]"><div className="h-full bg-[#6AAFF8]" style={{ width: `${(item.count / max) * 100}%` }} /></div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
