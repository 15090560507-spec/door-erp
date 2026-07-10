"use client";

import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { MODULE_OPTIONS } from "@/lib/types";
import type { ModuleName } from "@/lib/types";

export default function TopNav() {
  const { user, module, setModule, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const canOpenAdmin = ["超级管理员", "录入员", "绘图员"].includes(user?.role || "");
  const adminItems = [...MODULE_OPTIONS, { title: "后台管理", module: "后台管理" as ModuleName }];
  const items = canOpenAdmin ? adminItems : MODULE_OPTIONS;

  return (
    <nav className="sticky top-0 z-40 backdrop-blur-xl bg-white/80 border-b border-[#E5E5EA]/60 shadow-sm">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center gap-1.5 h-14">
          {/* Logo */}
          <span className="text-[15px] font-bold text-[#1C1C1E] mr-3 tracking-tight whitespace-nowrap">
            西州将军
          </span>

          {/* 模块导航按钮 */}
          {items.map((item) => {
            const active = module === item.module;
            return (
              <button
                key={item.module}
                onClick={() => {
                  setModule(item.module);
                  if (item.module === "报价系统") {
                    router.push("/quote");
                  } else if (item.module === "效果渲染") {
                    router.push("/render");
                  } else if (pathname !== "/dashboard") {
                    router.push("/dashboard");
                  }
                }}
                className={`
                  relative px-3.5 py-1.5 text-[13px] font-medium rounded-lg whitespace-nowrap
                  transition-all duration-200 cursor-pointer select-none
                  ${active
                    ? "bg-[#007AFF] text-white shadow-md shadow-[#007AFF]/25"
                    : "text-[#3C3C43]/70 hover:text-[#1C1C1E] hover:bg-[#F2F2F7]"
                  }
                `}
              >
                {item.title}
              </button>
            );
          })}

          <div className="flex-1" />

          {/* 用户信息 */}
          <span className="text-[12px] text-[#8E8E93] bg-[#F2F2F7] px-2.5 py-1 rounded-full font-medium">
            {user?.name}
          </span>

          {/* 退出 */}
          <button
            onClick={logout}
            className="text-[12px] font-medium text-[#FF3B30]/70 hover:text-[#FF3B30] hover:bg-[#FF3B30]/8 px-3 py-1.5 rounded-lg transition-all duration-200"
          >
            退出
          </button>
        </div>
      </div>
    </nav>
  );
}
