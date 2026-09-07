"use client";

import {
  CalendarDays,
  CheckCircle2,
  CircleAlert,
  FileStack,
  PencilLine,
  Plus,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import type { ComponentType } from "react";
import type { TaskOverviewData } from "@/lib/types";

interface Props {
  data: TaskOverviewData;
  activeStatus: string;
  onStatus: (status: string) => void;
  onQuery: (query: string) => void;
  onCreate: () => void;
  onRefresh: () => void;
}

const STATUS_META = [
  { status: "待绘制", color: "#DFF45F", text: "等待绘图" },
  { status: "待初审", color: "#73A7FF", text: "等待初审" },
  { status: "待终审", color: "#B298F2", text: "等待终审" },
  { status: "待修改", color: "#FF7D78", text: "退回修改" },
  { status: "已通过", color: "#65D394", text: "终审完成" },
] as const;

interface MetricDefinition {
  label: string;
  value: number;
  caption: string;
  status: string;
  tone: "dark" | "lime" | "plain" | "risk" | "success";
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}

export default function TaskOverviewDashboard({ data, activeStatus, onStatus, onQuery, onCreate, onRefresh }: Props) {
  const metrics: MetricDefinition[] = [
    { label: "全部图纸", value: data.total, caption: "累计录入图纸", status: "", tone: "dark", icon: FileStack },
    { label: "今日新增", value: data.today_created, caption: "今日新建任务", status: "", tone: "lime", icon: CalendarDays },
    { label: "待绘制", value: data.status_counts["待绘制"] || 0, caption: "等待绘图处理", status: "待绘制", tone: "plain", icon: PencilLine },
    { label: "待修改", value: data.status_counts["待修改"] || 0, caption: "需要优先处理", status: "待修改", tone: "risk", icon: CircleAlert },
    { label: "已通过", value: data.status_counts["已通过"] || 0, caption: "已完成终审", status: "已通过", tone: "success", icon: CheckCircle2 },
  ];

  return (
    <section className="overview-dashboard">
      <header className="overview-hero">
        <div>
          <div className="overview-eyebrow"><TrendingUp size={14} /> 图纸协同工作台</div>
          <h1>任务总览</h1>
          <p>集中查看图纸流转、积压风险、客户分布和门型结构。</p>
        </div>
        <div className="overview-hero__actions">
          <button type="button" className="overview-refresh" onClick={onRefresh} title="刷新任务数据"><RefreshCw size={16} />刷新</button>
          <button type="button" className="overview-create" onClick={onCreate}><Plus size={17} />图纸信息录入</button>
        </div>
      </header>

      <div className="overview-metrics">
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            metric={metric}
            active={Boolean(metric.status) && activeStatus === metric.status}
            onClick={metric.status ? () => onStatus(activeStatus === metric.status ? "" : metric.status) : undefined}
          />
        ))}
      </div>

      <div className="overview-primary-grid">
        <TrendPanel data={data} />
        <FlowPanel data={data} activeStatus={activeStatus} onStatus={onStatus} />
      </div>

      <div className="overview-secondary-grid">
        <Ranking title="客户图纸量" caption="按累计图纸数量排序" items={data.customers} onQuery={onQuery} />
        <Ranking title="门型分布" caption="当前产品结构占比" items={data.door_types} onQuery={onQuery} variant="soft" />
      </div>
    </section>
  );
}

function MetricCard({ metric, active, onClick }: { metric: MetricDefinition; active: boolean; onClick?: () => void }) {
  const Icon = metric.icon;
  const content = (
    <>
      <span className="overview-metric__icon"><Icon size={18} strokeWidth={1.8} /></span>
      <span className="overview-metric__label">{metric.label}</span>
      <strong>{metric.value}</strong>
      <small>{metric.caption}</small>
      {onClick && <span className="overview-metric__action">查看任务 <span aria-hidden="true">↗</span></span>}
    </>
  );
  const className = `overview-metric overview-metric--${metric.tone} ${active ? "is-active" : ""}`;
  return onClick
    ? <button type="button" className={className} onClick={onClick}>{content}</button>
    : <div className={className}>{content}</div>;
}

function TrendPanel({ data }: { data: TaskOverviewData }) {
  const width = 760;
  const height = 250;
  const top = 30;
  const bottom = 42;
  const left = 28;
  const right = 12;
  const plotHeight = height - top - bottom;
  const plotWidth = width - left - right;
  const max = Math.max(1, ...data.trend.flatMap((item) => [item.created, item.approved]));
  const slot = plotWidth / Math.max(1, data.trend.length);
  const barWidth = Math.max(5, Math.min(14, slot * 0.24));

  return (
    <section className="overview-panel overview-trend">
      <div className="overview-panel__header">
        <div><h2>近 14 天图纸流转</h2><p>新增任务与终审通过趋势</p></div>
        <div className="overview-legend"><span><i className="is-created" />新增</span><span><i className="is-approved" />终审通过</span></div>
      </div>
      <div className="overview-chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="近十四天新增任务与终审通过趋势图">
          {[0, 0.33, 0.66, 1].map((ratio) => {
            const y = top + plotHeight * ratio;
            return <line key={ratio} x1={left} x2={width - right} y1={y} y2={y} className="overview-chart-grid" />;
          })}
          {data.trend.map((item, index) => {
            const baseX = left + index * slot + slot / 2;
            const createdHeight = Math.max(item.created ? 3 : 0, (item.created / max) * plotHeight);
            const approvedHeight = Math.max(item.approved ? 3 : 0, (item.approved / max) * plotHeight);
            return (
              <g key={item.date}>
                <rect className="overview-bar overview-bar--created" x={baseX - barWidth - 2} y={top + plotHeight - createdHeight} width={barWidth} height={createdHeight} rx={barWidth / 2} style={{ animationDelay: `${index * 22}ms` }}><title>{`${item.label} 新增 ${item.created}`}</title></rect>
                <rect className="overview-bar overview-bar--approved" x={baseX + 2} y={top + plotHeight - approvedHeight} width={barWidth} height={approvedHeight} rx={barWidth / 2} style={{ animationDelay: `${index * 22 + 40}ms` }}><title>{`${item.label} 通过 ${item.approved}`}</title></rect>
                {(index % 2 === 0 || index === data.trend.length - 1) && <text x={baseX} y={height - 13} textAnchor="middle" className="overview-chart-label">{item.label}</text>}
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}

function FlowPanel({ data, activeStatus, onStatus }: { data: TaskOverviewData; activeStatus: string; onStatus: (status: string) => void }) {
  return (
    <section className="overview-panel overview-flow">
      <div className="overview-panel__header overview-panel__header--dark">
        <div><h2>流程健康度</h2><p>当前任务状态与积压占比</p></div>
        <span className="overview-total">{data.total} 项</span>
      </div>
      <div className="overview-flow__list">
        {STATUS_META.map((item) => {
          const count = data.status_counts[item.status] || 0;
          const ratio = data.total ? (count / data.total) * 100 : 0;
          const active = activeStatus === item.status;
          return (
            <button key={item.status} type="button" className={`overview-flow__item ${active ? "is-active" : ""}`} onClick={() => onStatus(active ? "" : item.status)}>
              <span className="overview-flow__name"><i style={{ backgroundColor: item.color }} />{item.status}<small>{item.text}</small></span>
              <strong>{count}</strong><span className="overview-flow__percent">{Math.round(ratio)}%</span>
              <span className="overview-flow__track"><i style={{ width: `${ratio}%`, backgroundColor: item.color }} /></span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function Ranking({ title, caption, items, onQuery, variant = "plain" }: {
  title: string;
  caption: string;
  items: { name: string; count: number }[];
  onQuery: (query: string) => void;
  variant?: "plain" | "soft";
}) {
  const max = Math.max(1, ...items.map((item) => item.count));
  const total = items.reduce((sum, item) => sum + item.count, 0);
  return (
    <section className={`overview-panel overview-ranking overview-ranking--${variant}`}>
      <div className="overview-panel__header"><div><h2>{title}</h2><p>{caption}</p></div><span className="overview-ranking__total">{total}</span></div>
      {items.length === 0 ? (
        <div className="overview-ranking__empty"><FileStack size={22} /><span>暂无可统计数据</span></div>
      ) : (
        <div className="overview-ranking__list">
          {items.slice(0, 8).map((item, index) => (
            <button key={item.name} type="button" onClick={() => onQuery(item.name)} className="overview-ranking__item">
              <span className="overview-ranking__index">{String(index + 1).padStart(2, "0")}</span>
              <span className="overview-ranking__main"><span><strong>{item.name}</strong><small>{item.count} 项</small></span><i><b style={{ width: `${(item.count / max) * 100}%` }} /></i></span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
