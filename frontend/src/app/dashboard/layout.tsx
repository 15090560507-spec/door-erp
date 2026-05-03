"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import TopNav from "@/components/TopNav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", background: "#F2F2F7"
      }}>
        <p style={{ color: "#8E8E93" }}>加载中...</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen" style={{ background: "#F2F2F7" }}>
      <div className="max-w-[1440px] mx-auto px-6">
        <TopNav />
        {children}
      </div>
    </div>
  );
}
