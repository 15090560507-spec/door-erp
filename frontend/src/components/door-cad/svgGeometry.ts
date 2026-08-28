import type { DoorCadPart, DoorCadPoint } from "@/lib/doorCadTypes";

export interface SvgBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export function svgPoint(point: DoorCadPoint) {
  return { x: point.x, y: -point.y };
}

export function svgPoints(points: DoorCadPoint[]) {
  return points.map((point) => {
    const value = svgPoint(point);
    return `${value.x},${value.y}`;
  }).join(" ");
}

export function partBounds(part: DoorCadPart): SvgBounds {
  const points = [
    ...part.cutOuter.points,
    ...part.holes.flatMap((shape) => shape.points),
    ...part.grooves.flatMap((groove) => groove.segments.flatMap((segment) => [segment.start, segment.end])),
  ];
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => -point.y);
  const shapeExtents = part.holes.flatMap((shape) => {
    if (!shape.center) return [];
    const width = shape.diameter ?? shape.width ?? 0;
    const height = shape.diameter ?? shape.height ?? 0;
    return [
      { x: shape.center.x - width / 2, y: -(shape.center.y - height / 2) },
      { x: shape.center.x + width / 2, y: -(shape.center.y + height / 2) },
    ];
  });
  xs.push(...shapeExtents.map((point) => point.x));
  ys.push(...shapeExtents.map((point) => point.y));
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

export function paddedBounds(bounds: SvgBounds, paddingRatio = 0.08): SvgBounds {
  const width = Math.max(bounds.maxX - bounds.minX, 1);
  const height = Math.max(bounds.maxY - bounds.minY, 1);
  const padding = Math.max(width, height) * paddingRatio;
  return {
    minX: bounds.minX - padding,
    minY: bounds.minY - padding,
    maxX: bounds.maxX + padding,
    maxY: bounds.maxY + padding,
  };
}

export function formatMillimetres(value: number) {
  return `${Number(value.toFixed(3))} mm`;
}
