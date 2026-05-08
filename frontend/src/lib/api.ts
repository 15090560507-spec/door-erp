import axios from "axios";
import type {
  LoginResponse, VerifyResponse,
  UserInfo,
  DoorFormData,
  TaskItem,
  TaskListResponse,
} from "./types";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
  timeout: 60000,
});

// ===================== Token 管理（sessionStorage: 关浏览器即清除） =====================
function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("door_token");
}

// 请求拦截器：自动附加 Authorization header
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 跳转登录页，超时/网络错误统一处理
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
    // 超时或网络错误：注入友好消息供上层显示
    if (error.code === "ECONNABORTED") {
      error.userMessage = "请求超时，请检查网络后重试";
    } else if (!error.response) {
      error.userMessage = "网络连接失败，请检查服务器状态";
    }
    return Promise.reject(error);
  }
);

// ===================== 用户 / 认证 =====================
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

export async function createUser(user: { uid: string; pwd: string; role: string; name: string }) {
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

// ===================== 任务 =====================
export async function getAllTasks(): Promise<TaskListResponse> {
  const { data } = await api.get<TaskListResponse>("/admin/tasks");
  return data;
}
export async function getTasks(params?: {
  date?: string;
  status?: string;
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
