interface Props {
  counts: Record<string, number>;
  onFilter: (stage: string) => void;
}

const cards = [
  ["BOM准备", "BOM 待填写"],
  ["缺料", "缺料"],
  ["下料", "待下料"],
  ["生产", "生产中"],
  ["质检", "待质检"],
  ["入库", "待入库"],
  ["发货", "待发货"],
  ["完成", "已完成"],
];

export default function ProductionDashboard({ counts, onFilter }: Props) {
  return (
    <section className="border-y border-[#E5E5EA] bg-white">
      <div className="grid grid-cols-2 gap-px bg-[#E5E5EA] sm:grid-cols-4 xl:grid-cols-8">
        {cards.map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => onFilter(key)}
            className="min-h-24 bg-white px-4 py-4 text-left transition-colors hover:bg-[#F8F8FA]"
          >
            <span className="block text-xs text-[#8E8E93]">{label}</span>
            <strong className="mt-2 block text-2xl font-semibold text-[#1C1C1E]">{counts[key] || 0}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}
