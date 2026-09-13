"use client";

import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import TopNav from "@/components/TopNav";
import { useAuth } from "@/hooks/useAuth";

const COLLAPSED_KEY = "door_sidebar_collapsed_v1";
const COLLAPSED_EVENT = "door-sidebar-collapsed-change";

function subscribeCollapsed(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(COLLAPSED_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(COLLAPSED_EVENT, callback);
  };
}

function getCollapsedSnapshot() {
  return localStorage.getItem(COLLAPSED_KEY) === "1";
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const collapsed = useSyncExternalStore(subscribeCollapsed, getCollapsedSnapshot, () => false);
  const [mobileState, setMobileState] = useState({ open: false, pathname });
  const mobileOpen = mobileState.open && mobileState.pathname === pathname;

  useEffect(() => {
    if (!mobileOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileState({ open: false, pathname });
    };
    document.body.classList.add("app-drawer-open");
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.classList.remove("app-drawer-open");
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileOpen, pathname]);

  const toggleCollapsed = () => {
    localStorage.setItem(COLLAPSED_KEY, collapsed ? "0" : "1");
    window.dispatchEvent(new Event(COLLAPSED_EVENT));
  };

  if (pathname === "/" || !user) return children;

  return (
    <div className={`app-shell ${collapsed ? "app-shell--collapsed" : ""}`}>
      <TopNav
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileState({ open: false, pathname })}
        onToggleCollapsed={toggleCollapsed}
        onOpenMobile={() => setMobileState({ open: true, pathname })}
      />
      <div className="app-shell__content">
        <div key={pathname} className="app-route-enter">{children}</div>
      </div>
    </div>
  );
}
