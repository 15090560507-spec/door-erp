import { api } from "./api";
import type {
  DoorCadDomainError,
  DoorCadGeometry,
  DoorCadProjectRecord,
  DoorCadProjectRequest,
  DoorCadProjectSummary,
} from "./doorCadTypes";

const BASE = "/door-cad/frame";

export async function calculateDoorFrame(request: DoorCadProjectRequest) {
  const { data } = await api.post<DoorCadGeometry>(`${BASE}/calculate`, request);
  return data;
}

export async function listDoorCadProjects() {
  const { data } = await api.get<{ projects: DoorCadProjectSummary[] }>(`${BASE}/projects`);
  return data.projects;
}

export async function getDoorCadProject(projectId: string) {
  const { data } = await api.get<DoorCadProjectRecord>(`${BASE}/projects/${projectId}`);
  return data;
}

export async function createDoorCadProject(request: DoorCadProjectRequest) {
  const { data } = await api.post<DoorCadProjectRecord>(`${BASE}/projects`, request);
  return data;
}

export async function updateDoorCadProject(projectId: string, request: DoorCadProjectRequest) {
  const { data } = await api.put<DoorCadProjectRecord>(`${BASE}/projects/${projectId}`, request);
  return data;
}

async function exportDoorCadFile(
  endpoint: "export-dxf" | "export-bom" | "export-json",
  body: { projectId?: string; inputs?: DoorCadProjectRequest["inputs"]; project?: DoorCadProjectRequest["project"]; acknowledgeWarnings: boolean },
) {
  try {
    const response = await api.post<Blob>(`${BASE}/${endpoint}`, body, {
      responseType: "blob",
      timeout: 120000,
    });
    return response.data;
  } catch (error: unknown) {
    const requestError = error as { response?: { data?: unknown }; userMessage?: string };
    if (requestError.response?.data instanceof Blob) {
      const raw = await requestError.response.data.text();
      try {
        const parsed = JSON.parse(raw) as { detail?: DoorCadDomainError | Array<{ msg?: string }> };
        if (parsed.detail && !Array.isArray(parsed.detail)) {
          requestError.userMessage = parsed.detail.message;
        } else if (Array.isArray(parsed.detail)) {
          requestError.userMessage = parsed.detail.map((item) => item.msg || "参数格式错误").join("；");
        }
      } catch {
        requestError.userMessage = raw || "导出失败";
      }
    }
    throw requestError;
  }
}

export function exportDoorCadDxf(body: Parameters<typeof exportDoorCadFile>[1]) {
  return exportDoorCadFile("export-dxf", body);
}

export function exportDoorCadBom(body: Parameters<typeof exportDoorCadFile>[1]) {
  return exportDoorCadFile("export-bom", body);
}

export function exportDoorCadJson(body: Parameters<typeof exportDoorCadFile>[1]) {
  return exportDoorCadFile("export-json", body);
}

export function downloadDoorCadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function doorCadErrorMessage(error: unknown, fallback = "操作失败") {
  const value = error as { userMessage?: string; message?: string; response?: { data?: { detail?: DoorCadDomainError } } };
  return value.userMessage || value.response?.data?.detail?.message || value.message || fallback;
}
