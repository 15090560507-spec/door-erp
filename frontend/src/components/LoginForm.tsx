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
    if (!ok) {
      setError("账号或密码错误！");
    }
    setLoading(false);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "#F2F2F7",
      }}
    >
      <div style={{ height: "10vh" }} />
      <h2
        style={{
          textAlign: "center",
          color: "#1C1C1E",
          fontWeight: 700,
          fontSize: 24,
          marginBottom: 8,
        }}
      >
        西州将军 - 智能协同平台
      </h2>
      <p style={{ textAlign: "center", color: "#8E8E93", marginBottom: 32 }}>
        Sign in to continue
      </p>

      <div
        style={{
          width: 380,
          maxWidth: "90vw",
          background: "white",
          borderRadius: 12,
          border: "1px solid rgba(0,0,0,0.05)",
          boxShadow: "0 4px 20px rgba(0,0,0,0.03)",
          padding: "32px 28px",
        }}
      >
        <form onSubmit={handleSubmit}>
          <label
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: "#8E8E93",
              display: "block",
              marginBottom: 4,
            }}
          >
            账号
          </label>
          <input
            type="text"
            value={uid}
            onChange={(e) => setUid(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 12px",
              fontSize: 14,
              borderRadius: 6,
              background: "#FAFAFC",
              border: "1px solid #C7C7CC",
              outline: "none",
              marginBottom: 16,
              boxSizing: "border-box",
              transition: "all 0.2s",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#007AFF";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(0,122,255,0.15)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#C7C7CC";
              e.currentTarget.style.boxShadow = "none";
            }}
          />

          <label
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: "#8E8E93",
              display: "block",
              marginBottom: 4,
            }}
          >
            密码
          </label>
          <input
            type="password"
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 12px",
              fontSize: 14,
              borderRadius: 6,
              background: "#FAFAFC",
              border: "1px solid #C7C7CC",
              outline: "none",
              marginBottom: 8,
              boxSizing: "border-box",
              transition: "all 0.2s",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#007AFF";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(0,122,255,0.15)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#C7C7CC";
              e.currentTarget.style.boxShadow = "none";
            }}
          />

          {error && (
            <p style={{ color: "#FF3B30", fontSize: 13, marginBottom: 12, marginTop: 4 }}>
              {error}
            </p>
          )}

          <div style={{ height: 10 }} />
          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "10px 0",
              background: loading ? "#80BDFF" : "#007AFF",
              color: "white",
              fontWeight: 700,
              fontSize: 14,
              border: "none",
              borderRadius: 8,
              cursor: loading ? "not-allowed" : "pointer",
              transition: "all 0.2s ease",
            }}
          >
            {loading ? "登录中..." : "登 录"}
          </button>
        </form>
      </div>
    </div>
  );
}
