export type FloatingPosition = { x: number; y: number };
export type FloatingSize = { width: number; height: number };
type Size = FloatingSize;
export const DEFAULT_FLOATING_SIZE: FloatingSize = { width: 510, height: 660 };

export function clampFloatingSize(size: FloatingSize, viewport: Size): FloatingSize {
  const widthLimit = Math.max(1, viewport.width - 16), heightLimit = Math.max(1, viewport.height - 16);
  return {
    width: Math.max(Math.min(280, widthLimit), Math.min(size.width, widthLimit)),
    height: Math.max(Math.min(240, heightLimit), Math.min(size.height, heightLimit)),
  };
}

export function shouldDockPreview(actionBottom: number, viewportHeight: number): boolean {
  return actionBottom <= viewportHeight;
}

export function clampFloatingPosition(position: FloatingPosition, panel: Size, viewport: Size): FloatingPosition {
  const margin = 8;
  return {
    x: Math.max(margin, Math.min(position.x, Math.max(margin, viewport.width - panel.width - margin))),
    y: Math.max(margin, Math.min(position.y, Math.max(margin, viewport.height - panel.height - margin))),
  };
}

export function initialFloatingPosition(viewport: Size): FloatingPosition {
  const panel = clampFloatingSize(DEFAULT_FLOATING_SIZE, viewport);
  return clampFloatingPosition({ x: viewport.width - panel.width - 16, y: 96 }, panel, viewport);
}
