"use client";

import { useAuth } from "@/hooks/useAuth";
import { MODULE_OPTIONS } from "@/lib/types";
import type { ModuleName } from "@/lib/types";

export default function TopNav() {
  const { user, module, setModule, logout } = useAuth();

  const adminItems = [...MODULE_OPTIONS, { title: "后台管理", module: "后台管理" as ModuleName }];
  const items = user?.role === "超级管理员" ? adminItems : MODULE_OPTIONS;

  const activeStyle: React.CSSProperties = {
    background: "#007AFF",
    color: "white",
    fontWeight: 700,
    border: "none",
    borderRadius: 8,
    boxShadow: "inset 0 4px 6px rgba(0,0,0,0.3)",
    transform: "translateY(2px)",
  };

  const inactiveStyle: React.CSSProperties = {
    background: "#FFFFFF",
    color: "#1C1C1E",
    fontWeight: 500,
    border: "1px solid #C7C7CC",
    borderRadius: 8,
    boxShadow: "0 4px 8px rgba(0,0,0,0.06)",
  };

  return (
    <div style={{ paddingTop: 10 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {items.map((item) => (
          <button
            key={item.module}
            onClick={() => setModule(item.module)}
            style={{
              ...(module === item.module ? activeStyle : inactiveStyle),
              padding: "8px 20px",
              fontSize: 14,
              border: module === item.module ? "none" : "1px solid #C7C7CC",
              cursor: "pointer",
              transition: "all 0.2s ease",
              whiteSpace: "nowrap",
            }}
            onMouseEnter={(e) => {
              if (module !== item.module) {
                e.currentTarget.style.borderColor = "#007AFF";
                e.currentTarget.style.color = "#007AFF";
                e.currentTarget.style.boxShadow = "0 6px 12px rgba(0,122,255,0.1)";
              }
            }}
            onMouseLeave={(e) => {
              if (module !== item.module) {
                e.currentTarget.style.borderColor = "#C7C7CC";
                e.currentTarget.style.color = "#1C1C1E";
                e.currentTarget.style.boxShadow = "0 4px 8px rgba(0,0,0,0.06)";
              }
            }}
          >
            {item.title}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <span style={{ color: "#8E8E93", fontSize: 13, marginRight: 12 }}>
          {user?.name}
        </span>
        <button
          onClick={logout}
          style={{
            padding: "8px 16px",
            background: "#FFF0F0",
            color: "#FF3B30",
            border: "1px solid #FFD1D1",
            borderRadius: 8,
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 600,
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#FF3B30";
            e.currentTarget.style.color = "white";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#FFF0F0";
            e.currentTarget.style.color = "#FF3B30";
          }}
        >
          退出
        </button>
      </div>
      <div style={{ height: 20 }} />
    </div>
  );
}
