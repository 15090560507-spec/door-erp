"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import TopNav from "@/components/TopNav";
import { useAuth } from "@/hooks/useAuth";

export default function DoorCadFrameLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, setModule } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/");
      return;
    }
    if (user.uid !== "A") {
      setModule("任务总览");
      router.replace("/dashboard");
    }
  }, [loading, router, setModule, user]);
  if (loading || !user || user.uid !== "A") return null;
  return <div className="min-h-screen bg-[#F2F2F7]"><TopNav />{children}</div>;
}
