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

  useEffect(() => {
    const stored = localStorage.getItem("door_user");
    const storedModule = localStorage.getItem("door_module");
    if (stored) {
      try {
        setUser(JSON.parse(stored));
        if (storedModule) setModule(storedModule as ModuleName);
      } catch {
        localStorage.removeItem("door_user");
      }
    }
    setLoading(false);
  }, []);

  const loginFn = async (uid: string, pwd: string): Promise<boolean> => {
    const { login: apiLogin } = await import("@/lib/api");
    const res = await apiLogin(uid, pwd);
    if (res.success && res.user) {
      setUser(res.user);
      setModule(res.user.default_module as ModuleName);
      localStorage.setItem("door_user", JSON.stringify(res.user));
      localStorage.setItem("door_module", res.user.default_module);
      router.push("/dashboard");
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
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
