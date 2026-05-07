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

const AuthContext = createContext<AuthCtx>({
  user: null,
  module: "图纸信息录入",
  loading: true,
  login: async () => false,
  logout: () => {},
  setModule: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [module, setModule] = useState<ModuleName>("图纸信息录入");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // 页面加载：通过 token 验证用户身份（而非直接信任 localStorage）
  useEffect(() => {
    let cancelled = false;

    const initAuth = async () => {
      const token = localStorage.getItem("door_token");
      if (!token) {
        // 无 token：清除所有残留数据
        localStorage.removeItem("door_user");
        localStorage.removeItem("door_module");
        if (!cancelled) setLoading(false);
        return;
      }

      // 有 token：调后端验证有效性
      try {
        const { verifyAuth: apiVerify } = await import("@/lib/api");
        const verified = await apiVerify();

        if (!cancelled && verified) {
          // token 有效 → 读取缓存的 user 信息（verify 端点不返回完整 UserInfo）
          const cached = localStorage.getItem("door_user");
          if (cached) {
            try {
              setUser(JSON.parse(cached));
            } catch {
              setUser({ uid: verified.uid, password: "", role: verified.role, name: verified.name, default_module: verified.default_module });
            }
          } else {
            setUser({ uid: verified.uid, password: "", role: verified.role, name: verified.name, default_module: verified.default_module });
          }
          const storedModule = localStorage.getItem("door_module");
          if (storedModule) setModule(storedModule as ModuleName);
        }

        if (!cancelled && !verified) {
          // token 无效/过期 → 清除并跳转登录
          localStorage.removeItem("door_token");
          localStorage.removeItem("door_user");
          localStorage.removeItem("door_module");
          router.replace("/");
        }
      } catch {
        // 网络异常：保留 token 和缓存数据，允许继续使用
        const cached = localStorage.getItem("door_user");
        if (cached) {
          try { setUser(JSON.parse(cached)); } catch {}
        }
        const storedModule = localStorage.getItem("door_module");
        if (storedModule) setModule(storedModule as ModuleName);
      }

      if (!cancelled) setLoading(false);
    };

    initAuth();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loginFn = async (uid: string, pwd: string): Promise<boolean> => {
    const { login: apiLogin } = await import("@/lib/api");
    const res = await apiLogin(uid, pwd);
    if (res.success && res.user && res.token) {
      setUser(res.user);
      setModule(res.user.default_module as ModuleName);
      // 存储 token + user 信息
      localStorage.setItem("door_token", res.token);
      localStorage.setItem("door_user", JSON.stringify(res.user));
      localStorage.setItem("door_module", res.user.default_module);
      router.push("/dashboard");
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("door_token");
    localStorage.removeItem("door_user");
    localStorage.removeItem("door_module");
    router.push("/");
  };

  const changeModule = (m: ModuleName) => {
    setModule(m);
    localStorage.setItem("door_module", m);
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
