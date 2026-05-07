"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";

export default function LoginForm() {
  const { login } = useAuth();
  const [uid, setUid] = useState("");
  const [pwd, setPwd] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const ok = await login(uid, pwd);
      if (!ok) setError("账号或密码错误");
    } catch {
      setError("网络连接失败，请检查服务器状态");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-zinc-100 p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
            </svg>
          </div>
          <h1 className="text-[22px] font-bold text-zinc-800 tracking-tight">西州将军铜门</h1>
          <p className="text-[13px] text-zinc-400 mt-1">生产图纸协同系统</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl p-6 shadow-sm border border-zinc-200/60">
          <div className="mb-4">
            <label className="block text-[13px] font-medium text-zinc-500 mb-1.5">账号</label>
            <input
              type="text"
              value={uid}
              onChange={(e) => setUid(e.target.value)}
              placeholder="请输入账号"
              autoFocus
              className="w-full px-4 py-2.5 text-sm rounded-xl bg-zinc-50 border border-transparent outline-none transition-all duration-200 focus:border-blue-500 focus:bg-white focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
            />
          </div>
          <div className="mb-4">
            <label className="block text-[13px] font-medium text-zinc-500 mb-1.5">密码</label>
            <input
              type="password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              placeholder="请输入密码"
              className="w-full px-4 py-2.5 text-sm rounded-xl bg-zinc-50 border border-transparent outline-none transition-all duration-200 focus:border-blue-500 focus:bg-white focus:shadow-[0_0_0_3px_rgba(59,130,246,0.12)]"
            />
          </div>

          {error && (
            <div className="text-[13px] text-red-500 text-center py-2 mb-3 bg-red-50 rounded-lg">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !uid || !pwd}
            className="w-full py-2.5 rounded-xl bg-blue-600 text-white font-semibold text-sm
              hover:bg-blue-700 active:scale-[0.98] transition-all duration-200
              disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100
              shadow-md shadow-blue-500/20"
          >
            {loading ? "登录中..." : "登 录"}
          </button>
        </form>

        <p className="text-center text-[11px] text-zinc-400 mt-4">
          如需账号请联系系统管理员
        </p>
        <p className="text-center text-[11px] text-zinc-300 mt-1">
          关闭浏览器将自动退出登录
        </p>
      </div>
    </div>
  );
}
