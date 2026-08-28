import type { DoorCadGeometry } from "@/lib/doorCadTypes";
import GeometryViewport from "./GeometryViewport";
import { paddedBounds } from "./svgGeometry";

interface Props {
  geometry: DoorCadGeometry | null;
}

export default function Overview2D({ geometry }: Props) {
  if (!geometry) {
    return <GeometryViewport bounds={{ minX: 0, minY: 0, maxX: 1, maxY: 1 }} label="门框装配总览" empty />;
  }

  const { assembly, parts } = geometry;
  const bounds = paddedBounds({ minX: 0, minY: 0, maxX: assembly.width, maxY: assembly.height }, 0.06);
  const partMap = new Map(parts.map((part) => [part.partId, part]));

  return (
    <GeometryViewport bounds={bounds} label={`门框装配总览 · ${assembly.width} × ${assembly.height} mm`}>
      <g>
        {assembly.placements.map((placement) => {
          const part = partMap.get(placement.partId);
          const y = assembly.height - placement.y - placement.height;
          const skin = part?.materialType === "skin";
          return (
            <g key={placement.partId}>
              <rect
                x={placement.x}
                y={y}
                width={placement.width}
                height={placement.height}
                fill={skin ? "rgba(0,122,255,0.12)" : "rgba(52,199,89,0.13)"}
                stroke={skin ? "#007AFF" : "#248A3D"}
                strokeWidth={Math.max(assembly.width / 650, 1.5)}
              />
              <text
                x={placement.x + placement.width / 2}
                y={y + placement.height / 2}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={Math.max(assembly.width / 60, 18)}
                fill="#1C1C1E"
              >
                {placement.partId}
              </text>
            </g>
          );
        })}
        <rect x={0} y={0} width={assembly.width} height={assembly.height} fill="none" stroke="#1C1C1E" strokeWidth={3} />
      </g>
    </GeometryViewport>
  );
}
