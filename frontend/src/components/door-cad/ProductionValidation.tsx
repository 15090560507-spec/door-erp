import type { DoorCadGeometry } from "@/lib/doorCadTypes";

export default function ProductionValidation({ geometry }: { geometry: DoorCadGeometry | null }) {
  if (!geometry) return null;
  const report = geometry.validation;
  const tone = report.status === "ERROR"
    ? "border-[#FF3B30]/30 bg-[#FF3B30]/6 text-[#C5221F]"
    : report.status === "WARNING"
      ? "border-[#FF9500]/35 bg-[#FF9500]/7 text-[#9A5B00]"
      : "border-[#34C759]/30 bg-[#34C759]/7 text-[#248A3D]";
  return (
    <section className={`border px-4 py-3 ${tone}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">生产校验：{report.status}</h3>
        <span className="text-xs">{report.errors.length} 个错误 · {report.warnings.length} 个警告</span>
      </div>
      {[...report.errors, ...report.warnings].length > 0 && (
        <ul className="mt-2 space-y-1 text-[13px]">
          {[...report.errors, ...report.warnings].map((issue) => (
            <li key={`${issue.code}-${issue.field}`}>[{issue.code}] {issue.message}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
