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
    const ok = await login(uid, pwd);
    if (!ok) setError("账号或密码错误！");
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#F2F2F7] to-[#E5E5EA] p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[#007AFF] to-[#5856D6] flex items-center justify-center shadow-lg shadow-[#007AFF]/25">
            <span className="text-2xl font-bold text-white">西</span>
          </div>
          <h1 className="text-[22px] font-bold text-[#1C1C1E] tracking-tight">西州将军铜门</h1>
          <p className="text-[13px] text-[#8E8E93] mt-1">生产图纸协同系统</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E5EA]">
          <div className="mb-4">
            <label className="block text-[13px] font-medium text-[#8E8E93] mb-1.5">账号</label>
            <input
              type="text"
              value={uid}
              onChange={(e) => setUid(e.target.value)}
              placeholder="请输入账号"
              autoFocus
              className="w-full px-4 py-2.5 text-sm rounded-xl bg-[#F2F2F7] border border-transparent outline-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.12)]"
            />
          </div>
          <div className="mb-4">
            <label className="block text-[13px] font-medium text-[#8E8E93] mb-1.5">密码</label>
            <input
              type="password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              placeholder="请输入密码"
              className="w-full px-4 py-2.5 text-sm rounded-xl bg-[#F2F2F7] border border-transparent outline-none transition-all duration-200 focus:border-[#007AFF] focus:bg-white focus:shadow-[0_0_0_3px_rgba(0,122,255,0.12)]"
            />
          </div>

          {error && (
            <div className="text-[13px] text-[#FF3B30] text-center py-1.5 mb-3 bg-[#FFEBEB] rounded-lg">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !uid || !pwd}
            className="w-full py-2.5 rounded-xl bg-[#007AFF] text-white font-semibold text-sm
              hover:bg-[#0062CC] active:scale-[0.98] transition-all duration-200
              disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100
              shadow-md shadow-[#007AFF]/20"
          >
            {loading ? "登录中..." : "登录"}
          </button>
        </form>

        <p className="text-center text-[11px] text-[#8E8E93] mt-4">
          如需账号请联系系统管理员
        </p>
      </div>
    </div>
  );
}
