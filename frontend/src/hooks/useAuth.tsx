"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { UserInfo, ModuleName } from "@/lib/types";
import { MODULE_OPTIONS } from "@/lib/types";

interface AuthCtx {
  user: UserInfo | null;
  loading: boolean;
  login: (uid: string, pwd: string) => Promise<boolean>;
  logout: () => void;
  setModule: (m: ModuleName) => void;
}

// ===================== 存储层：sessionStorage =====================
// 关闭浏览器 → 自动清除 → 下次访问必须重新登录
const S = {
  getToken: () => sessionStorage.getItem("door_token"),
  setToken: (v: string) => sessionStorage.setItem("door_token", v),
  getUser: (): UserInfo | null => {
    try { const u = sessionStorage.getItem("door_user"); return u ? JSON.parse(u) : null; }
    catch { return null; }
  },
  setUser: (v: UserInfo) => sessionStorage.setItem("door_user", JSON.stringify(v)),
  getModule: () => sessionStorage.getItem("door_module"),
  setModule: (v: string) => sessionStorage.setItem("door_module", v),
  clear: () => { sessionStorage.removeItem("door_token"); sessionStorage.removeItem("door_user"); sessionStorage.removeItem("door_module"); },
};

// Cookie（session 级，不设 max-age → 关浏览器即清除）
function setAuthCookie(token: string) {
  document.cookie = `auth_token=${token}; path=/; SameSite=Lax`;
}
function clearAuthCookie() {
  document.cookie = "auth_token=; path=/; max-age=0";
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => false,
  logout: () => {},
  setModule: () => {},
});

// 模块单独拆成一个 context：切换模块只重渲染 TopNav 与依赖模块内容的页面，
// 避免所有消费 useAuth 的页面（效果渲染/生产管理等大页面）跟着重渲染造成卡顿。
const ModuleContext = createContext<ModuleName>("图纸信息录入");

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [module, setModule] = useState<ModuleName>("图纸信息录入");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const changeModule = useCallback((m: ModuleName) => {
    setModule(m);
    S.setModule(m);
  }, []);

  // 监听 401 事件：API 拦截器检测到 token 过期时触发
  useEffect(() => {
    const handle401 = () => {
      setUser(null);
      clearAuthCookie();
      router.replace("/");
    };
    window.addEventListener("auth-401", handle401);
    return () => window.removeEventListener("auth-401", handle401);
  }, [router]);

  // 页面加载：通过 token 验证用户身份
  useEffect(() => {
    let cancelled = false;

    const initAuth = async () => {
      const token = S.getToken();
      if (!token) {
        S.clear();
        clearAuthCookie();
        if (!cancelled) setLoading(false);
        return;
      }

      try {
        const { verifyAuth: apiVerify } = await import("@/lib/api");
        const verified = await apiVerify();

        if (!cancelled && verified) {
          const cached = S.getUser();
          if (cached) {
            setUser({ ...cached, permissions: verified.permissions || cached.permissions || [] });
          } else {
            setUser({
              uid: verified.uid,
              role: verified.role,
              name: verified.name,
              default_module: verified.default_module,
              permissions: verified.permissions || [],
            });
          }
          const m = S.getModule();
          if (m === "汇总看板" || m === "后台管理") {
            setModule("任务总览");
            S.setModule("任务总览");
          } else if (m && MODULE_OPTIONS.some((option) => option.module === m)) {
            setModule(m as ModuleName);
          }
        }

        if (!cancelled && !verified) {
          S.clear();
          clearAuthCookie();
          router.replace("/");
        }
      } catch {
        S.clear();
        clearAuthCookie();
        if (!cancelled) router.replace("/");
      }

      if (!cancelled) setLoading(false);
    };

    initAuth();
    return () => { cancelled = true; };
  }, [router]); // eslint-disable-line react-hooks/exhaustive-deps

  const loginFn = useCallback(async (uid: string, pwd: string): Promise<boolean> => {
    try {
      const { login: apiLogin } = await import("@/lib/api");
      const res = await apiLogin(uid, pwd);
      if (res.success && res.user && res.token) {
        setUser(res.user);
        S.setToken(res.token);
        S.setUser(res.user);
        S.setModule("图纸信息录入");
        setModule("图纸信息录入");
        setAuthCookie(res.token);
        router.push("/dashboard");
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [router]);

  const logout = useCallback(() => {
    setUser(null);
    S.clear();
    clearAuthCookie();
    router.push("/");
  }, [router]);

  const authValue = useMemo<AuthCtx>(
    () => ({ user, loading, login: loginFn, logout, setModule: changeModule }),
    [user, loading, loginFn, logout, changeModule]
  );

  return (
    <ModuleContext.Provider value={module}>
      <AuthContext.Provider value={authValue}>
        {children}
      </AuthContext.Provider>
    </ModuleContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

/** 当前模块（只应被需要按模块切换内容的组件使用，如 TopNav、任务工作台）。 */
export function useModule() {
  return useContext(ModuleContext);
}
