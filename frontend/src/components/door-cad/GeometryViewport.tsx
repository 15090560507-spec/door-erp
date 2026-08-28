import type { ReactNode } from "react";
import type { SvgBounds } from "./svgGeometry";

interface Props {
  bounds: SvgBounds;
  children: ReactNode;
  label: string;
  empty?: boolean;
}

export default function GeometryViewport({ bounds, children, label, empty = false }: Props) {
  const width = Math.max(bounds.maxX - bounds.minX, 1);
  const height = Math.max(bounds.maxY - bounds.minY, 1);

  return (
    <div className="relative min-h-[420px] overflow-hidden border border-[#D1D1D6] bg-white">
      <div className="absolute left-3 top-3 z-10 bg-white/90 px-2 py-1 text-[12px] font-medium text-[#3C3C43]">
        {label}
      </div>
      {empty ? (
        <div className="flex min-h-[420px] items-center justify-center text-sm text-[#8E8E93]">暂无几何数据</div>
      ) : (
        <svg
          role="img"
          aria-label={label}
          className="h-[420px] w-full"
          viewBox={`${bounds.minX} ${bounds.minY} ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
        >
          <rect x={bounds.minX} y={bounds.minY} width={width} height={height} fill="#FAFAFA" />
          {children}
        </svg>
      )}
    </div>
  );
}
