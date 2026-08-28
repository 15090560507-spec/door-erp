import type { DoorCadPart, DoorCadShape } from "@/lib/doorCadTypes";
import GeometryViewport from "./GeometryViewport";
import { paddedBounds, partBounds, svgPoint, svgPoints } from "./svgGeometry";

interface Props {
  part: DoorCadPart | null;
}

function ShapeView({ shape }: { shape: DoorCadShape }) {
  if (shape.center) {
    const center = svgPoint(shape.center);
    if (shape.kind === "circle") {
      return <circle cx={center.x} cy={center.y} r={(shape.diameter ?? 0) / 2} fill="none" stroke="#FF3B30" strokeWidth={0.8} />;
    }
    return (
      <rect
        x={center.x - (shape.width ?? shape.diameter ?? 0) / 2}
        y={center.y - (shape.height ?? shape.diameter ?? 0) / 2}
        width={shape.width ?? shape.diameter ?? 0}
        height={shape.height ?? shape.diameter ?? 0}
        fill="none"
        stroke="#FF3B30"
        strokeWidth={0.8}
      />
    );
  }
  return <polyline points={svgPoints(shape.points)} fill="none" stroke="#FF3B30" strokeWidth={0.8} />;
}

export default function PartDetail2D({ part }: Props) {
  if (!part) {
    return <GeometryViewport bounds={{ minX: 0, minY: 0, maxX: 1, maxY: 1 }} label="零件展开详情" empty />;
  }
  const bounds = paddedBounds(partBounds(part), 0.06);
  const strokeWidth = Math.max(part.flatWidth / 200, 0.6);

  return (
    <GeometryViewport bounds={bounds} label={`${part.partId} · ${part.name} · ${part.flatWidth} × ${part.length} mm`}>
      <polygon points={svgPoints(part.cutOuter.points)} fill="rgba(0,122,255,0.06)" stroke="#1C1C1E" strokeWidth={strokeWidth} />
      {part.grooves.flatMap((groove) => groove.segments.map((segment, index) => {
        const start = svgPoint(segment.start);
        const end = svgPoint(segment.end);
        return (
          <line
            key={`${groove.grooveId}-${index}`}
            x1={start.x}
            y1={start.y}
            x2={end.x}
            y2={end.y}
            stroke={groove.face === "inner" ? "#AF52DE" : "#FF9500"}
            strokeWidth={strokeWidth}
            strokeDasharray={`${strokeWidth * 5} ${strokeWidth * 3}`}
          />
        );
      }))}
      {part.holes.map((shape) => <ShapeView key={shape.shapeId} shape={shape} />)}
      {part.dimensions.map((dimension) => {
        const start = svgPoint(dimension.start);
        const end = svgPoint(dimension.end);
        return (
          <g key={dimension.dimensionId}>
            <line x1={start.x} y1={start.y} x2={end.x} y2={end.y} stroke="#636366" strokeWidth={strokeWidth * 0.75} />
            <text
              x={(start.x + end.x) / 2}
              y={(start.y + end.y) / 2 - 3}
              textAnchor="middle"
              fontSize={Math.max(part.flatWidth / 15, 6)}
              fill="#3C3C43"
            >
              {dimension.label}
            </text>
          </g>
        );
      })}
    </GeometryViewport>
  );
}
