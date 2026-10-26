import type { RenderReferenceRole } from "./renderApi";

export const RENDER_CATEGORIES = ["门扇款式", "拉手", "合页", "颜色", "门套款式", "花件"];

export function renderCategoryLabel(value: string): string {
  if (["门扇", "款式"].includes(value)) return "门扇款式";
  if (["包套", "门套"].includes(value)) return "门套款式";
  return value;
}

export function renderCategoryRole(value: string, colorTarget: RenderReferenceRole = "panel"): RenderReferenceRole {
  const category = renderCategoryLabel(value);
  if (["颜色", "纹理"].includes(category)) return colorTarget;
  if (category === "门扇款式") return "panel";
  if (["门套款式", "门头"].includes(category)) return "trim";
  if (category === "门框") return "frame";
  if (category === "玻璃") return "glass";
  return "hardware";
}
