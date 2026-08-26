import axios from "axios";
import type {
  DoorFormData,
  LayeredRenderRecord,
  LoginResponse,
  TaskItem,
  TaskListResponse,
  UserInfo,
  VerifyResponse,
} from "./types";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
  timeout: 60000,
});

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("door_token");
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        sessionStorage.removeItem("door_token");
        sessionStorage.removeItem("door_user");
        sessionStorage.removeItem("door_module");
        document.cookie = "auth_token=; path=/; max-age=0";
        window.dispatchEvent(new Event("auth-401"));
      }
    }

    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      error.userMessage = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      error.userMessage = detail.map((item) => item?.msg || JSON.stringify(item)).join("; ");
    } else if (detail && typeof detail === "object") {
      const detailMessage = extractApiErrorMessage(detail);
      if (detailMessage) error.userMessage = detailMessage;
    } else if (error.code === "ECONNABORTED") {
      error.userMessage = "请求超时，请检查网络后重试";
    } else if (!error.response) {
      error.userMessage = "网络连接失败，请检查服务器状态";
    }

    return Promise.reject(error);
  }
);

function extractApiErrorMessage(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return cleanupApiErrorText(value);
  if (Array.isArray(value)) {
    return value.map((item) => extractApiErrorMessage(item)).filter(Boolean).join("; ");
  }
  if (typeof value !== "object") return "";
  const record = value as Record<string, unknown>;
  for (const key of ["message", "errorMessage", "error", "reason"]) {
    const item = record[key];
    if (typeof item === "string" && item.trim()) return cleanupApiErrorText(item);
  }
  if (record.detail) return extractApiErrorMessage(record.detail);
  return "";
}

function cleanupApiErrorText(text: string): string {
  const value = (text || "").trim();
  if (/^\s*<!doctype html/i.test(value) || /^\s*<html/i.test(value)) {
    const title = value.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]?.replace(/\s+/g, " ").trim();
    return title ? `上游返回 HTML 页面：${title}` : "上游返回 HTML 页面，不是接口 JSON";
  }
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

export async function login(uid: string, pwd: string): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>("/login", { uid, pwd });
  return data;
}

export async function verifyAuth(): Promise<VerifyResponse | null> {
  try {
    const { data } = await api.get<VerifyResponse>("/auth/verify");
    return data;
  } catch {
    return null;
  }
}

export async function getUsers(): Promise<{ users: Record<string, UserInfo>; total: number }> {
  const { data } = await api.get("/users");
  return data;
}

export async function createUser(user: { uid: string; pwd: string; role: string; name: string; permissions?: string[] }) {
  const { data } = await api.post("/users", user);
  return data;
}

export async function deleteUser(uid: string) {
  const { data } = await api.delete(`/users/${uid}`);
  return data;
}

export async function resetPassword(uid: string, newPwd: string) {
  const { data } = await api.put(`/users/${uid}/reset-password`, { new_pwd: newPwd });
  return data;
}

export async function getAllTasks(): Promise<TaskListResponse> {
  const { data } = await api.get<TaskListResponse>("/admin/tasks");
  return data;
}

export async function getTasks(params?: {
  date?: string;
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<TaskListResponse> {
  const { data } = await api.get<TaskListResponse>("/tasks", { params });
  return data;
}

export async function getTask(taskId: string): Promise<TaskItem> {
  const { data } = await api.get<TaskItem>(`/tasks/${taskId}`);
  return data;
}

export async function createTask(req: {
  params: DoorFormData;
  ref_text: string;
  ref_images: string[];
}): Promise<TaskItem> {
  const { data } = await api.post<TaskItem>("/tasks", req);
  return data;
}

export async function updateTask(
  taskId: string,
  update: {
    status?: string;
    params?: DoorFormData;
    drawing_img_b64?: string | null;
    review_feedback?: string;
    ref_text?: string;
    ref_images?: string[];
    quote_status?: string;
    confirm_status?: string;
  }
): Promise<TaskItem> {
  const { data } = await api.put<TaskItem>(`/tasks/${taskId}`, update);
  return data;
}

export async function deleteTask(taskId: string) {
  const { data } = await api.delete(`/tasks/${taskId}`);
  return data;
}

const DROPDOWN_CACHE_KEY = "door_dropdown_options_cache_v4";

export async function loadDropdownOptions(): Promise<Record<string, string[]>> {
  if (typeof window !== "undefined") {
    const cached = sessionStorage.getItem(DROPDOWN_CACHE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed && Object.keys(parsed).length > 0) return parsed;
      } catch {
        // ignore broken cache
      }
    }
  }

  try {
    const { data } = await api.get("/admin/dropdown-options");
    const options = data.options || {};
    if (typeof window !== "undefined" && Object.keys(options).length > 0) {
      sessionStorage.setItem(DROPDOWN_CACHE_KEY, JSON.stringify(options));
    }
    return options;
  } catch {
    return {};
  }
}

export async function generateCad(formData: DoorFormData): Promise<Blob> {
  try {
    const { data } = await api.post("/generate_cad", formData, {
      responseType: "blob",
    });
    return data;
  } catch (error: unknown) {
    const requestError = error as {
      response?: { data?: unknown };
      userMessage?: string;
    };
    const body = requestError.response?.data;
    if (body instanceof Blob) {
      const text = await body.text();
      try {
        const parsed = JSON.parse(text) as unknown;
        requestError.userMessage = extractApiErrorMessage(parsed) || cleanupApiErrorText(text);
      } catch {
        requestError.userMessage = cleanupApiErrorText(text);
      }
    }
    throw requestError;
  }
}

export async function generateCadPreview(formData: DoorFormData): Promise<string> {
  try {
    const { data } = await api.post<string>("/generate_cad_preview", formData, {
      responseType: "text",
    });
    return data;
  } catch (error: unknown) {
    const requestError = error as {
      response?: { data?: unknown };
      userMessage?: string;
    };
    const body = requestError.response?.data;
    if (typeof body === "string" && body.trim()) {
      try {
        requestError.userMessage = extractApiErrorMessage(JSON.parse(body)) || cleanupApiErrorText(body);
      } catch {
        requestError.userMessage = cleanupApiErrorText(body);
      }
    }
    throw requestError;
  }
}

export async function generateLayeredRender(input: {
  taskId: string;
  dpi?: number;
  targetLongEdge?: number;
  faces?: string;
  modelConfigId?: string;
  referenceAssetIds?: string[];
}): Promise<{ record: LayeredRenderRecord }> {
  const { data } = await api.post<{ record: LayeredRenderRecord }>("/layered-render/generate", input, {
    timeout: 300000,
  });
  return data;
}

export async function listLayeredRecords(limit = 30): Promise<{ records: LayeredRenderRecord[] }> {
  const { data } = await api.get<{ records: LayeredRenderRecord[] }>("/layered-render/records", {
    params: { limit },
  });
  return data;
}

export async function deleteLayeredRecord(recordId: string) {
  const { data } = await api.delete(`/layered-render/records/${recordId}`);
  return data;
}

/** 通过带鉴权头的请求下载后端文件（PSD/JPG 等），避免 cookie/代理导致的下载失败。 */
export async function downloadFileFromUrl(url: string, filename: string): Promise<void> {
  const requestPath = url.startsWith("/api/") ? url.slice(4) : url;
  const { data } = await api.get<Blob>(requestPath, { responseType: "blob", timeout: 180000 });
  downloadCadBlob(data, filename);
}

export function downloadCadBlob(blob: Blob, filename: string) {
  const downloadBlob = blob.type === "application/octet-stream"
    ? blob
    : new Blob([blob], { type: "application/octet-stream" });
  const url = window.URL.createObjectURL(downloadBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
}
