import axios from "axios";
import type {
  LoginResponse,
  UserInfo,
  DoorFormData,
  TaskItem,
  TaskListResponse,
} from "./types";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
  timeout: 60000,
});

// ===================== 用户 =====================
export async function login(uid: string, pwd: string): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>("/login", { uid, pwd });
  return data;
}

export async function getUsers(): Promise<{ users: Record<string, UserInfo>; total: number }> {
  const { data } = await api.get("/users");
  return data;
}

export async function createUser(user: { uid: string; pwd: string; role: string; name: string }) {
  const { data } = await api.post("/users", user);
  return data;
}

export async function deleteUser(uid: string) {
  const { data } = await api.delete(`/users/${uid}`);
  return data;
}

// ===================== 任务 =====================
export async function getTasks(params?: {
  date?: string;
  status?: string;
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
  ref_img_b64: string | null;
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
  }
): Promise<TaskItem> {
  const { data } = await api.put<TaskItem>(`/tasks/${taskId}`, update);
  return data;
}

export async function deleteTask(taskId: string) {
  const { data } = await api.delete(`/tasks/${taskId}`);
  return data;
}

// ===================== CAD 生成 =====================
export async function generateCad(formData: DoorFormData): Promise<Blob> {
  const { data } = await api.post("/generate_cad", formData, {
    responseType: "blob",
  });
  return data;
}

export function downloadCadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
