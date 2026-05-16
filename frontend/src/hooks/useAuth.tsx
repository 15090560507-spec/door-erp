"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { UserInfo, ModuleName } from "@/lib/types";

interface AuthCtx {
  user: UserInfo | null;
  module: ModuleName;
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
  getModule: () => sessionStorage.getItem("door_module") as ModuleName | null,
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
  module: "汇总看板",
  loading: true,
  login: async () => false,
  logout: () => {},
  setModule: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [module, setModule] = useState<ModuleName>("汇总看板");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

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
            setUser(cached);
          } else {
            setUser({ uid: verified.uid, password: "", role: verified.role, name: verified.name, default_module: verified.default_module });
          }
          const m = S.getModule();
          if (m) setModule(m);
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
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loginFn = async (uid: string, pwd: string): Promise<boolean> => {
    try {
      const { login: apiLogin } = await import("@/lib/api");
      const res = await apiLogin(uid, pwd);
      if (res.success && res.user && res.token) {
        setUser(res.user);
        setModule("汇总看板");
        S.setToken(res.token);
        S.setUser(res.user);
        S.setModule("汇总看板");
        setAuthCookie(res.token);
        router.push("/dashboard");
        return true;
      }
      return false;
    } catch {
      return false;
    }
  };

  const logout = () => {
    setUser(null);
    S.clear();
    clearAuthCookie();
    router.push("/");
  };

  const changeModule = (m: ModuleName) => {
    setModule(m);
    S.setModule(m);
  };

  return (
    <AuthContext.Provider value={{ user, module, loading, login: loginFn, logout, setModule: changeModule }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
