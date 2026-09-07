"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ComponentType } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  BadgeCheck,
  Calculator,
  ChevronLeft,
  ClipboardCheck,
  ClipboardList,
  Database,
  Factory,
  LayoutDashboard,
  LogOut,
  Menu,
  PackageSearch,
  PanelLeftClose,
  PanelLeftOpen,
  PencilRuler,
  Pin,
  PinOff,
  Scissors,
  ShoppingCart,
  Sparkles,
  Warehouse,
  X,
} from "lucide-react";
import { useAuth, useModule } from "@/hooks/useAuth";
import { MODULE_OPTIONS, type ModuleName } from "@/lib/types";

const DRAWING_MODULES: ModuleName[] = ["任务总览", "图纸绘制", "图纸初审", "图纸终审"];
const BUSINESS_MODULES: ModuleName[] = ["订单确认", "生产管理", "采购管理", "库存管理", "基础资料"];
const PINNED_KEY = "door_business_pinned_modules_v1";

const MODULE_ICONS: Record<ModuleName, ComponentType<{ size?: number; strokeWidth?: number }>> = {
  任务总览: LayoutDashboard,
  图纸信息录入: PencilRuler,
  图纸绘制: PencilRuler,
  图纸初审: ClipboardCheck,
  图纸终审: BadgeCheck,
  下料: Scissors,
  效果渲染: Sparkles,
  报价系统: Calculator,
  订单确认: ClipboardList,
  生产管理: Factory,
  采购管理: ShoppingCart,
  库存管理: Warehouse,
  基础资料: Database,
};

function moduleRoute(module: ModuleName) {
  if (DRAWING_MODULES.includes(module)) return "/dashboard";
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

function moduleFromPath(pathname: string): ModuleName | null {
  if (pathname.startsWith("/quote")) return "报价系统";
  if (pathname.startsWith("/render")) return "效果渲染";
  if (pathname.startsWith("/door-cad/frame")) return "下料";
  if (pathname.startsWith("/orders")) return "订单确认";
  if (pathname.startsWith("/production")) return "生产管理";
  if (pathname.startsWith("/purchasing")) return "采购管理";
  if (pathname.startsWith("/inventory")) return "库存管理";
  if (pathname.startsWith("/master-data")) return "基础资料";
  return null;
}

interface TopNavProps {
  collapsed: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onOpenMobile: () => void;
  onToggleCollapsed: () => void;
}

export default function TopNav({ collapsed, mobileOpen, onCloseMobile, onOpenMobile, onToggleCollapsed }: TopNavProps) {
  const { user, setModule, logout } = useAuth();
  const dashboardModule = useModule();
  const pathname = usePathname();
  const router = useRouter();
  const [pinned, setPinned] = useState<ModuleName[]>([]);

  const availableItems = useMemo(
    () => MODULE_OPTIONS.filter((item) => item.module !== "下料" || user?.uid === "A"),
    [user?.uid],
  );
  const drawingItems = availableItems.filter((item) => !BUSINESS_MODULES.includes(item.module));
  const businessItems = availableItems.filter((item) => BUSINESS_MODULES.includes(item.module));
  const pinnedItems = availableItems.filter((item) => pinned.includes(item.module));
  const pathModule = moduleFromPath(pathname);
  const activeModule = pathname.startsWith("/dashboard") ? dashboardModule : (pathModule || dashboardModule);

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(PINNED_KEY) || "[]") as string[];
      setPinned(stored.filter((item): item is ModuleName => MODULE_OPTIONS.some((option) => option.module === item)));
    } catch {
      setPinned([]);
    }
  }, []);

  const togglePinned = (module: ModuleName) => {
    setPinned((current) => {
      const next = current.includes(module) ? current.filter((item) => item !== module) : [...current, module];
      localStorage.setItem(PINNED_KEY, JSON.stringify(next));
      return next;
    });
  };

  const handleNavigate = (module: ModuleName) => {
    if (DRAWING_MODULES.includes(module)) setModule(module);
    onCloseMobile();
  };

  const renderItem = (item: { title: string; module: ModuleName }, allowPin = false) => {
    const Icon = MODULE_ICONS[item.module];
    const active = activeModule === item.module;
    const isPinned = pinned.includes(item.module);
    const href = moduleRoute(item.module);
    return (
      <div key={item.module} className="app-sidebar__item-wrap">
        <Link
          href={href}
          prefetch
          aria-current={active ? "page" : undefined}
          aria-label={item.title}
          title={collapsed ? item.title : undefined}
          onMouseEnter={() => router.prefetch(href)}
          onFocus={() => router.prefetch(href)}
          onClick={() => handleNavigate(item.module)}
          className={`app-sidebar__item ${active ? "is-active" : ""}`}
        >
          <span className="app-sidebar__icon"><Icon size={19} strokeWidth={1.8} /></span>
          <span className="app-sidebar__label">{item.title}</span>
        </Link>
        {allowPin && !collapsed && (
          <button
            type="button"
            className={`app-sidebar__pin ${isPinned ? "is-pinned" : ""}`}
            onClick={() => togglePinned(item.module)}
            aria-label={isPinned ? `取消固定${item.title}` : `固定${item.title}`}
            title={isPinned ? "取消固定" : "固定到顶部"}
          >
            {isPinned ? <PinOff size={14} /> : <Pin size={14} />}
          </button>
        )}
      </div>
    );
  };

  return (
    <>
      <header className="app-mobile-bar">
        <button type="button" className="app-icon-button" onClick={onOpenMobile} aria-label="打开导航"><Menu size={21} /></button>
        <div className="app-mobile-brand"><span className="app-brand-mark">西</span><span>西州将军</span></div>
        <span className="app-mobile-page">{activeModule}</span>
      </header>

      {mobileOpen && <button type="button" className="app-sidebar__scrim" onClick={onCloseMobile} aria-label="关闭导航" />}

      <aside className={`app-sidebar ${mobileOpen ? "is-mobile-open" : ""}`} aria-label="主导航">
        <div className="app-sidebar__brand">
          <span className="app-brand-mark">西</span>
          <span className="app-sidebar__brand-copy"><strong>西州将军</strong><small>Door ERP</small></span>
          <button type="button" className="app-sidebar__mobile-close" onClick={onCloseMobile} aria-label="关闭导航"><X size={20} /></button>
        </div>

        <nav className="app-sidebar__nav">
          {pinnedItems.length > 0 && (
            <section className="app-sidebar__group">
              <div className="app-sidebar__group-title"><Pin size={12} /><span>已固定</span></div>
              {pinnedItems.map((item) => renderItem(item, true))}
            </section>
          )}
          <section className="app-sidebar__group">
            <div className="app-sidebar__group-title"><PackageSearch size={12} /><span>图纸业务</span></div>
            {drawingItems.map((item) => renderItem(item))}
          </section>
          <section className="app-sidebar__group">
            <div className="app-sidebar__group-title"><Factory size={12} /><span>经营管理</span></div>
            {businessItems.map((item) => renderItem(item, true))}
          </section>
        </nav>

        <div className="app-sidebar__footer">
          <div className="app-sidebar__user" title={collapsed ? user?.name : undefined}>
            <span className="app-sidebar__avatar">{user?.name?.slice(-1) || user?.uid}</span>
            <span className="app-sidebar__user-copy"><strong>{user?.name}</strong><small>{user?.role}</small></span>
          </div>
          <button type="button" className="app-sidebar__footer-button" onClick={logout} aria-label="退出登录" title="退出登录">
            <LogOut size={18} /><span>退出登录</span>
          </button>
          <button type="button" className="app-sidebar__collapse" onClick={onToggleCollapsed} aria-label={collapsed ? "展开导航" : "收起导航"} title={collapsed ? "展开导航" : "收起导航"}>
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            <span>{collapsed ? "展开" : "收起导航"}</span>
            {!collapsed && <ChevronLeft size={14} />}
          </button>
        </div>
      </aside>
    </>
  );
}
