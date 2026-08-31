"use client";

import { useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth, useModule } from "@/hooks/useAuth";
import { MODULE_OPTIONS } from "@/lib/types";

export default function TopNav() {
  const { user, setModule, logout } = useAuth();
  const activeModule = useModule();
  const router = useRouter();
  const pathname = usePathname();
  const activeItemRef = useRef<HTMLButtonElement>(null);

  const items = MODULE_OPTIONS.filter((item) => item.module !== "下料" || user?.uid === "A");

  useEffect(() => {
    activeItemRef.current?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [activeModule]);

  return (
    <nav className="sticky top-0 z-40 w-full border-b border-[#E5E5EA]/60 bg-white/80 shadow-sm backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl min-w-0 items-center px-3 sm:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {/* Logo */}
          <span className="text-[15px] font-bold text-[#1C1C1E] mr-3 tracking-tight whitespace-nowrap">
            西州将军
          </span>

          {/* 模块导航按钮 */}
          {items.map((item) => {
            const active = activeModule === item.module;
            return (
              <button
                key={item.module}
                ref={active ? activeItemRef : undefined}
                onClick={() => {
                  setModule(item.module);
                  if (item.module === "报价系统") {
                    router.push("/quote");
                  } else if (item.module === "效果渲染") {
                    router.push("/render");
                  } else if (item.module === "生产管理") {
                    router.push("/production");
                  } else if (item.module === "下料") {
                    router.push("/door-cad/frame");
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

        </div>

        {/* 用户操作固定在导航右侧，模块过多时仅滚动中间导航区。 */}
        <div className="ml-2 flex shrink-0 items-center gap-1 bg-white/80">
          <span className="hidden max-w-24 truncate rounded-full bg-[#F2F2F7] px-2.5 py-1 text-[12px] font-medium text-[#8E8E93] sm:block">
            {user?.name}
          </span>
          <button
            onClick={logout}
            className="rounded-lg px-2 py-1.5 text-[12px] font-medium text-[#FF3B30]/70 transition-all duration-200 hover:bg-[#FF3B30]/8 hover:text-[#FF3B30] sm:px-3"
          >
            退出
          </button>
        </div>
      </div>
    </nav>
  );
}
