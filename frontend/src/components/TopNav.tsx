"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth, useModule } from "@/hooks/useAuth";
import { MODULE_OPTIONS, type ModuleName } from "@/lib/types";

const BUSINESS_MODULES: ModuleName[] = ["订单确认", "生产管理", "采购管理", "库存管理", "基础资料"];
const PINNED_KEY = "door_business_pinned_modules_v1";

function moduleRoute(module: ModuleName) {
  if (module === "报价系统") return "/quote";
  if (module === "效果渲染") return "/render";
  if (module === "下料") return "/door-cad/frame";
  if (module === "订单确认") return "/orders";
  if (module === "生产管理") return "/production";
  if (module === "采购管理") return "/purchasing";
  if (module === "库存管理") return "/inventory";
  if (module === "基础资料") return "/master-data";
  return "/dashboard";
}

export default function TopNav() {
  const { user, setModule, logout } = useAuth();
  const activeModule = useModule();
  const router = useRouter();
  const pathname = usePathname();
  const activeItemRef = useRef<HTMLButtonElement>(null);
  const businessMenuRef = useRef<HTMLDivElement>(null);
  const [businessOpen, setBusinessOpen] = useState(false);
  const [pinned, setPinned] = useState<ModuleName[]>([]);

  const availableItems = useMemo(
    () => MODULE_OPTIONS.filter((item) => item.module !== "下料" || user?.uid === "A"),
    [user?.uid],
  );
  const primaryItems = availableItems.filter((item) => !BUSINESS_MODULES.includes(item.module));
  const businessItems = availableItems.filter((item) => BUSINESS_MODULES.includes(item.module));
  const pinnedItems = businessItems.filter((item) => pinned.includes(item.module));

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(PINNED_KEY) || "[]") as string[];
      setPinned(stored.filter((item): item is ModuleName => BUSINESS_MODULES.includes(item as ModuleName)));
    } catch {
      setPinned([]);
    }
  }, []);

  useEffect(() => {
    activeItemRef.current?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [activeModule]);

  useEffect(() => {
    if (!businessOpen) return;
    const close = (event: MouseEvent) => {
      if (!businessMenuRef.current?.contains(event.target as Node)) setBusinessOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [businessOpen]);

  const go = (module: ModuleName) => {
    setModule(module);
    setBusinessOpen(false);
    const destination = moduleRoute(module);
    if (pathname !== destination) router.push(destination);
  };

  const togglePinned = (module: ModuleName) => {
    setPinned((current) => {
      const next = current.includes(module) ? current.filter((item) => item !== module) : [...current, module];
      localStorage.setItem(PINNED_KEY, JSON.stringify(next));
      return next;
    });
  };

  const renderModuleButton = (item: { title: string; module: ModuleName }) => {
    const active = activeModule === item.module;
    return (
      <button
        key={item.module}
        ref={active ? activeItemRef : undefined}
        onClick={() => go(item.module)}
        className={`relative whitespace-nowrap rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors ${
          active ? "bg-[#007AFF] text-white shadow-sm" : "text-[#3C3C43]/75 hover:bg-[#F2F2F7] hover:text-[#1C1C1E]"
        }`}
      >
        {item.title}
      </button>
    );
  };

  const businessActive = BUSINESS_MODULES.includes(activeModule);

  return (
    <nav className="sticky top-0 z-40 w-full border-b border-[#E5E5EA] bg-white/95 shadow-sm backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-[1680px] min-w-0 items-center px-3 sm:px-6">
        <span className="mr-3 shrink-0 whitespace-nowrap text-[15px] font-bold text-[#1C1C1E]">西州将军</span>

        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {primaryItems.map(renderModuleButton)}
          {pinnedItems.map(renderModuleButton)}
        </div>

        <div ref={businessMenuRef} className="relative ml-2 shrink-0">
          <button
            type="button"
            aria-expanded={businessOpen}
            onClick={() => setBusinessOpen((open) => !open)}
            className={`h-8 rounded-md border px-3 text-[13px] font-medium transition-colors ${
              businessActive && !pinned.includes(activeModule)
                ? "border-[#007AFF] bg-[#EDF6FF] text-[#007AFF]"
                : "border-[#D1D1D6] bg-white text-[#3C3C43] hover:bg-[#F2F2F7]"
            }`}
          >
            业务管理 <span aria-hidden="true">⌄</span>
          </button>
          {businessOpen && (
            <div className="absolute right-0 top-10 w-64 border border-[#D1D1D6] bg-white p-2 shadow-xl">
              <div className="px-2 pb-2 pt-1 text-xs font-medium text-[#8E8E93]">角色工作台</div>
              {businessItems.map((item) => {
                const active = activeModule === item.module;
                const isPinned = pinned.includes(item.module);
                return (
                  <div key={item.module} className={`flex items-center ${active ? "bg-[#EDF6FF]" : "hover:bg-[#F7F7F9]"}`}>
                    <button type="button" onClick={() => go(item.module)} className="min-w-0 flex-1 px-3 py-2.5 text-left text-sm">
                      <span className={active ? "font-semibold text-[#007AFF]" : "text-[#1C1C1E]"}>{item.title}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => togglePinned(item.module)}
                      className="mr-2 h-7 border border-[#D1D1D6] px-2 text-[11px] text-[#636366] hover:border-[#007AFF] hover:text-[#007AFF]"
                      title={isPinned ? "从顶部取消固定" : "固定到顶部"}
                    >
                      {isPinned ? "取消固定" : "固定"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="ml-2 flex shrink-0 items-center gap-1 border-l border-[#E5E5EA] pl-2">
          <span className="hidden max-w-24 truncate bg-[#F2F2F7] px-2.5 py-1 text-[12px] font-medium text-[#8E8E93] sm:block">{user?.name}</span>
          <button onClick={logout} className="px-2 py-1.5 text-[12px] font-medium text-[#D70015] hover:bg-[#FFF0F0] sm:px-3">退出</button>
        </div>
      </div>
    </nav>
  );
}
