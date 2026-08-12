import type { ProductionOrder } from "@/lib/productionTypes";

interface Props {
  orders: ProductionOrder[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export default function ProductionOrderList({ orders, selectedId, onSelect }: Props) {
  return (
    <div className="overflow-x-auto border border-[#E5E5EA] bg-white">
      <table className="min-w-[1220px] w-full table-fixed text-sm">
        <colgroup>
          <col className="w-40" />
          <col className="w-48" />
          <col className="w-48" />
          <col className="w-28" />
          <col className="w-28" />
          <col className="w-28" />
          <col className="w-32" />
          <col className="w-32" />
          <col className="w-36" />
          <col className="w-36" />
        </colgroup>
        <thead className="bg-[#F7F7F9] text-left text-xs text-[#636366]">
          <tr>
            {['生产单号', '客户/订货单位', '项目', '阶段', '进度', '缺料', '负责人', '状态', '要求交期', '最近更新'].map((label) => (
              <th key={label} className="border-b border-[#E5E5EA] px-3 py-3 font-medium">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr
              key={order.id}
              onClick={() => onSelect(order.id)}
              className={`cursor-pointer border-b border-[#F2F2F7] transition-colors ${selectedId === order.id ? 'bg-[#EAF3FF]' : 'hover:bg-[#FAFAFC]'}`}
            >
              <td className="px-3 py-3 font-semibold text-[#007AFF]">{order.order_no}</td>
              <td className="truncate px-3 py-3">{order.customer}</td>
              <td className="truncate px-3 py-3 text-[#636366]">{order.project || '-'}</td>
              <td className="px-3 py-3">{order.stage}</td>
              <td className="px-3 py-3"><Progress stage={order.stage} /></td>
              <td className={`px-3 py-3 ${order.shortage_status === '缺料' ? 'text-[#FF3B30]' : ''}`}>{order.shortage_status}</td>
              <td className="truncate px-3 py-3" title={order.owner || order.producer}>{order.owner || order.producer || '-'}</td>
              <td className="px-3 py-3">{order.status}</td>
              <td className={`px-3 py-3 ${dueClass(order.due_date, order.status)}`}>{order.due_date || '-'}</td>
              <td className="px-3 py-3 text-xs text-[#636366]">{formatTime(order.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {orders.length === 0 && <div className="px-5 py-12 text-center text-sm text-[#8E8E93]">暂无生产订单</div>}
    </div>
  );
}

const stages = ['BOM准备', '备料', '下料', '生产', '质检', '入库', '发货', '完成'];
function Progress({ stage }: { stage: string }) {
  const index = Math.max(0, stages.indexOf(stage));
  const percent = Math.round(((index + 1) / stages.length) * 100);
  return <div className="flex items-center gap-2"><span className="h-1.5 flex-1 bg-[#E5E5EA]"><span className="block h-full bg-[#007AFF]" style={{ width: `${percent}%` }} /></span><span className="w-8 text-right text-xs text-[#636366]">{percent}%</span></div>;
}
function dueClass(value: string, status: string) {
  if (!value || ['已完成', '已作废', '已撤回'].includes(status)) return 'text-[#636366]';
  const due = new Date(`${value}T23:59:59`).getTime();
  const days = (due - Date.now()) / 86400000;
  if (days < 0) return 'font-semibold text-[#FF3B30]';
  if (days <= 3) return 'font-semibold text-[#C76E00]';
  return 'text-[#636366]';
}
function formatTime(value: string) { return value ? value.replace('T', ' ').slice(0, 16) : '-'; }
