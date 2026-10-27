export type PatternSlot = "panel_b2" | "back_panel_b2" | "child_panel_b2" | "child_back_panel_b2" | "transom";
export type PatternDefinition = {
  version?: 1; name: string; paths: Array<{ points: [number, number][]; closed: boolean }>;
  stretch_x: [number, number]; stretch_y: [number, number]; warnings: string[];
};
export type PatternPlacement = {
  definition: PatternDefinition; band_width: number; inset: number;
  detail_x: number; detail_y: number; mirror: boolean; source_job_id: string;
};
export type AppliedPattern = PatternPlacement & { reviewed: true };
export type PatternJob = { id: string; status: "queued" | "running" | "completed" | "failed"; model: string; definition: PatternDefinition | null; error: string };
export type PatternTemplate = { id: string; name: string; snapshot: AppliedPattern };
export type PatternPreview = { loops: [number, number][][]; width: number; height: number; band_width: number };
export const REFERENCE_STYLE = "参考图线稿";
export function placementOf(snapshot: AppliedPattern): PatternPlacement {
  const { definition, band_width, inset, detail_x, detail_y, mirror, source_job_id } = snapshot;
  return { definition, band_width, inset, detail_x, detail_y, mirror, source_job_id };
}
