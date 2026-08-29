"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import TopNav from "@/components/TopNav";
import { useAuth } from "@/hooks/useAuth";

export default function DoorCadFrameLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!loading && !user) router.replace("/"); }, [loading, router, user]);
  if (loading || !user) return null;
  return <div className="min-h-screen bg-[#F2F2F7]"><TopNav />{children}</div>;
}
