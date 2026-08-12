interface Props {
  counts: Record<string, number>;
  onFilter: (stage: string) => void;
}

const cards = [
  ["待下达", "待下达", "text-[#9A6700]"],
  ["今日下达", "今日下达", "text-[#007AFF]"],
  ["即将到期", "即将到期", "text-[#C76E00]"],
  ["已逾期", "已逾期", "text-[#FF3B30]"],
  ["缺料", "缺料", "text-[#FF3B30]"],
  ["下料", "待下料", "text-[#1C1C1E]"],
  ["生产", "生产中", "text-[#007AFF]"],
  ["质检", "待质检", "text-[#AF52DE]"],
  ["入库", "待入库", "text-[#248A3D]"],
  ["发货", "待发货", "text-[#248A3D]"],
  ["完成", "已完成", "text-[#248A3D]"],
] as const;

export default function ProductionDashboard({ counts, onFilter }: Props) {
  return (
    <section className="border-y border-[#E5E5EA] bg-white">
      <div className="grid grid-cols-2 gap-px bg-[#E5E5EA] sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-11">
        {cards.map(([key, label, color]) => (
          <button
            key={key}
            type="button"
            onClick={() => onFilter(key)}
            className="min-h-24 bg-white px-3 py-4 text-left transition-colors hover:bg-[#F8F8FA]"
          >
            <span className="block text-xs text-[#8E8E93]">{label}</span>
            <strong className={`mt-2 block text-2xl font-semibold ${color}`}>{counts[key] || 0}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}
