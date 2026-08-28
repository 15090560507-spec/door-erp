import type { DoorCadPart } from "@/lib/doorCadTypes";
import { formatMillimetres } from "./svgGeometry";

export default function BomTable({ parts }: { parts: DoorCadPart[] }) {
  return (
    <div className="overflow-x-auto border border-[#D1D1D6] bg-white">
      <table className="w-full table-fixed text-[13px]">
        <thead className="bg-[#F2F2F7] text-[#3C3C43]">
          <tr>
            <th className="w-28 px-3 py-2 text-left">零件编号</th>
            <th className="px-3 py-2 text-left">名称</th>
            <th className="w-20 px-3 py-2 text-left">位置</th>
            <th className="w-20 px-3 py-2 text-left">材质</th>
            <th className="w-28 px-3 py-2 text-right">长度</th>
            <th className="w-28 px-3 py-2 text-right">展开宽</th>
            <th className="w-24 px-3 py-2 text-right">厚度</th>
            <th className="w-16 px-3 py-2 text-right">数量</th>
          </tr>
        </thead>
        <tbody>
          {parts.length === 0 ? (
            <tr><td colSpan={8} className="px-3 py-8 text-center text-[#8E8E93]">计算后显示物料清单</td></tr>
          ) : parts.map((part) => (
            <tr key={part.partId} className="border-t border-[#E5E5EA] text-[#1C1C1E]">
              <td className="px-3 py-2 font-mono">{part.partId}</td>
              <td className="px-3 py-2">{part.name}</td>
              <td className="px-3 py-2">{{ left: "左", right: "右", top: "上", bottom: "下" }[part.position]}</td>
              <td className="px-3 py-2">{part.materialType === "skeleton" ? "骨架" : "外皮"}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatMillimetres(part.length)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatMillimetres(part.flatWidth)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{formatMillimetres(part.thickness)}</td>
              <td className="px-3 py-2 text-right tabular-nums">1</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
