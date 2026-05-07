interface Props {
  status: string;
}

const badgeMap: Record<string, { bg: string; text: string; dot: string }> = {
  "待绘制":   { bg: "bg-[#E8E8ED]", text: "text-[#48484A]", dot: "bg-[#8E8E93]" },
  "待初审":   { bg: "bg-[#FFF3E0]", text: "text-[#CC7A00]", dot: "bg-[#FF9500]" },
  "待终审":   { bg: "bg-[#FFF3E0]", text: "text-[#CC7A00]", dot: "bg-[#FF9500]" },
  "待修改":   { bg: "bg-[#FFEBEB]", text: "text-[#CC2F2A]", dot: "bg-[#FF3B30]" },
  "已通过":   { bg: "bg-[#E5F9E5]", text: "text-[#248A3D]", dot: "bg-[#34C759]" },
};

export default function StatusBadge({ status }: Props) {
  const style = badgeMap[status] || { bg: "bg-[#E8E8ED]", text: "text-[#48484A]", dot: "bg-[#8E8E93]" };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${style.bg} ${style.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {status}
    </span>
  );
}
