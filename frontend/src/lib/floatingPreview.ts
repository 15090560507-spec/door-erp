export type FloatingPosition = { x: number; y: number };
type Size = { width: number; height: number };

export function clampFloatingPosition(position: FloatingPosition, panel: Size, viewport: Size): FloatingPosition {
  const margin = 8;
  return {
    x: Math.max(margin, Math.min(position.x, Math.max(margin, viewport.width - panel.width - margin))),
    y: Math.max(margin, Math.min(position.y, Math.max(margin, viewport.height - panel.height - margin))),
  };
}

export function initialFloatingPosition(viewport: Size): FloatingPosition {
  return clampFloatingPosition({ x: viewport.width - 356, y: 96 },
    { width: Math.min(340, viewport.width - 16), height: 260 }, viewport);
}
