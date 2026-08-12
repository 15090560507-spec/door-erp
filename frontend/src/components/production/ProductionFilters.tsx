"use client";

import type { ProductionOrderFilters } from "@/lib/productionTypes";

const emptyFilters: ProductionOrderFilters = {
  q: "", stage: "", status: "", owner: "", shortage: "", due_from: "", due_to: "",
};

export default function ProductionFilters({
  value,
  onChange,
  onApply,
}: {
  value: ProductionOrderFilters;
  onChange: (value: ProductionOrderFilters) => void;
  onApply: (value: ProductionOrderFilters) => void;
}) {
  const set = (key: keyof ProductionOrderFilters, next: string) => onChange({ ...value, [key]: next });
  return <section className="border border-[#E5E5EA] bg-white p-4">
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
      <label className="text-xs text-[#636366] xl:col-span-2"><span className="mb-1 block">搜索</span><input value={value.q || ''} onChange={(event) => set('q', event.target.value)} onKeyDown={(event) => event.key === 'Enter' && onApply(value)} placeholder="生产单号、客户、项目" className="h-10 w-full border border-[#C7C7CC] px-3 text-sm" /></label>
      <Select label="阶段" value={value.stage || ''} onChange={(next) => set('stage', next)} options={['BOM准备', '备料', '下料', '生产', '质检', '入库', '发货', '完成']} />
      <Select label="状态" value={value.status || ''} onChange={(next) => set('status', next)} options={['进行中', '已暂停', '已撤回', '已作废', '已完成']} />
      <Select label="缺料" value={value.shortage || ''} onChange={(next) => set('shortage', next)} options={['未知', '不缺料', '缺料']} />
      <Field label="负责人" value={value.owner || ''} onChange={(next) => set('owner', next)} />
      <div className="flex items-end gap-2"><button onClick={() => onApply(value)} className="h-10 flex-1 bg-[#007AFF] px-4 text-sm text-white">查询</button><button onClick={() => { onChange(emptyFilters); onApply(emptyFilters); }} className="h-10 border border-[#C7C7CC] px-3 text-sm">清空</button></div>
    </div>
    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:max-w-xl"><Field type="date" label="交期从" value={value.due_from || ''} onChange={(next) => set('due_from', next)} /><Field type="date" label="交期至" value={value.due_to || ''} onChange={(next) => set('due_to', next)} /></div>
  </section>;
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) { return <label className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm"><option value="">全部</option>{options.map((item) => <option key={item}>{item}</option>)}</select></label>; }
function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; type?: string }) { return <label className="text-xs text-[#636366]"><span className="mb-1 block">{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full border border-[#C7C7CC] px-3 text-sm" /></label>; }
