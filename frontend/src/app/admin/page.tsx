"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

export default function AdminPage() {
  const { loading, setModule } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    setModule("任务总览");
    router.replace("/dashboard");
  }, [loading, router, setModule]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F2F2F7]">
      <p className="text-sm text-[#8E8E93]">正在进入任务总览...</p>
    </div>
  );
}
