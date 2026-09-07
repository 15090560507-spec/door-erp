"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import TopNav from "@/components/TopNav";
import { useAuth } from "@/hooks/useAuth";

const COLLAPSED_KEY = "door_sidebar_collapsed_v1";

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "1");
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.body.classList.add("app-drawer-open");
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.classList.remove("app-drawer-open");
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileOpen]);

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current;
      localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
      return next;
    });
  };

  if (pathname === "/" || !user) return children;

  return (
    <div className={`app-shell ${collapsed ? "app-shell--collapsed" : ""}`}>
      <TopNav
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggleCollapsed={toggleCollapsed}
        onOpenMobile={() => setMobileOpen(true)}
      />
      <div className="app-shell__content">
        <div key={pathname} className="app-route-enter">{children}</div>
      </div>
    </div>
  );
}
