export const GLASS_LINE_STYLE_LABELS: Record<string, string> = {
  "单圈外围线": "单圈外围线（玻璃）",
};

const INSET_PATTERNS = new Set([
  "单圈外围线", "单圈外围线(封闭)", "四角回纹", "双边框",
  "双边框+花件", "六格线条", "八格线条",
]);
const SPACING_PATTERNS = new Set([
  "竖条", "四角回纹", "双边框", "双边框+花件", "六格线条", "八格线条",
]);

export function panelGlassControlScope(style: string, b2: string, b4: string) {
  const regions = style === "H+型布局"
    ? [{ name: "B2", pattern: b2 }, { name: "B4", pattern: b4 }]
    : style === "H型布局" ? [{ name: "B2", pattern: b2 }] : [];
  const inset = regions.filter(({ pattern }) => INSET_PATTERNS.has(pattern));
  const spacing = regions.filter(({ pattern }) => SPACING_PATTERNS.has(pattern));
  return {
    insetRegions: inset.map(({ name }) => name).join("/"),
    spacingRegions: spacing.map(({ name }) => name).join("/"),
    spacingIsBarsOnly: spacing.length > 0 && spacing.every(({ pattern }) => pattern === "竖条"),
  };
}
