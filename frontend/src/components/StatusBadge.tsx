interface Props {
  status: string;
}

const badgeStyle: Record<string, string> = {
  "待绘制": "bg-[#F2F2F7] text-[#1C1C1E]",
  "待初审": "bg-[#FFF5E5] text-[#FF9500]",
  "待终审": "bg-[#FFF5E5] text-[#FF9500]",
  "待修改": "bg-[#FFE5E5] text-[#FF3B30]",
  "已通过": "bg-[#E5FBE5] text-[#34C759]",
};

export default function StatusBadge({ status }: Props) {
  const cls = badgeStyle[status] || "bg-[#F2F2F7] text-[#1C1C1E]";
  return (
    <span className={`inline-block px-3 py-1 rounded-xl text-xs font-semibold ${cls}`}>
      {status}
    </span>
  );
}
