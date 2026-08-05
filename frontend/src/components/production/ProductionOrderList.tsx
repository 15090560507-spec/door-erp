import type { ProductionOrder } from "@/lib/productionTypes";

interface Props {
  orders: ProductionOrder[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export default function ProductionOrderList({ orders, selectedId, onSelect }: Props) {
  return (
    <div className="overflow-x-auto border border-[#E5E5EA] bg-white">
      <table className="min-w-[880px] w-full table-fixed text-sm">
        <colgroup>
          <col className="w-40" />
          <col className="w-48" />
          <col className="w-48" />
          <col className="w-28" />
          <col className="w-28" />
          <col className="w-28" />
          <col className="w-36" />
        </colgroup>
        <thead className="bg-[#F7F7F9] text-left text-xs text-[#636366]">
          <tr>
            {['生产单号', '客户/订货单位', '项目', '阶段', '缺料', '状态', '要求交期'].map((label) => (
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
              <td className={`px-3 py-3 ${order.shortage_status === '缺料' ? 'text-[#FF3B30]' : ''}`}>{order.shortage_status}</td>
              <td className="px-3 py-3">{order.status}</td>
              <td className="px-3 py-3 text-[#636366]">{order.due_date || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {orders.length === 0 && <div className="px-5 py-12 text-center text-sm text-[#8E8E93]">暂无生产订单</div>}
    </div>
  );
}
