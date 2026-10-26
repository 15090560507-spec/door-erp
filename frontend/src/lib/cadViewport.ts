export type CadViewBox = { x: number; y: number; width: number; height: number };

export function panCadView(box: CadViewBox, dx: number, dy: number): CadViewBox {
  return { ...box, x: box.x - dx, y: box.y - dy };
}

export function zoomCadView(box: CadViewBox, base: CadViewBox, anchor: { x: number; y: number }, dy: number): CadViewBox {
  const scale = Math.max(base.width / 8, Math.min(base.width * 8, box.width * Math.exp(dy * 0.008))) / box.width;
  return {
    x: anchor.x + (box.x - anchor.x) * scale,
    y: anchor.y + (box.y - anchor.y) * scale,
    width: box.width * scale,
    height: box.height * scale,
  };
}
