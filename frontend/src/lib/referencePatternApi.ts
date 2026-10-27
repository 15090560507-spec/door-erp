import { api } from "./api";
import type { AppliedPattern, PatternJob, PatternPlacement, PatternPreview, PatternTemplate } from "./referencePatternTypes";

export async function getPatternConnection() {
  return (await api.get<{ configured: boolean; model: string }>("/reference-patterns/connection")).data;
}
export async function recognizePattern(file: File, requestKey: string) {
  const body = new FormData(); body.append("file", file); body.append("request_key", requestKey);
  return (await api.post<{ job: PatternJob }>("/reference-patterns/jobs", body)).data.job;
}
export async function getPatternJob(id: string) {
  return (await api.get<{ job: PatternJob }>(`/reference-patterns/jobs/${id}`)).data.job;
}
export async function getPatternSource(id: string) {
  return (await api.get<Blob>(`/reference-patterns/jobs/${id}/source`, { responseType: "blob" })).data;
}
export async function previewPattern(placement: PatternPlacement, width: number, height: number, signal?: AbortSignal) {
  return (await api.post<PatternPreview>("/reference-patterns/preview", { placement, width, height }, { signal })).data;
}
export async function listPatternTemplates() {
  return (await api.get<{ templates: PatternTemplate[] }>("/reference-patterns/templates")).data.templates;
}
export async function savePatternTemplate(name: string, snapshot: AppliedPattern) {
  return (await api.post<{ template: PatternTemplate }>("/reference-patterns/templates", { name, snapshot })).data.template;
}
