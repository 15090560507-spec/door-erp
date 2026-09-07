"use client";

import { useState } from "react";
import PurchasingCenter from "@/components/inventory/PurchasingCenter";
import SupplyRequirements from "@/components/inventory/SupplyRequirements";

export default function PurchasingPage() {
  const [tab, setTab] = useState<"requirements" | "orders">("requirements");
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const notify = (message: string, error = false) => setNotice({ message, error });
  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]"><main className="mx-auto max-w-[1680px] space-y-4 px-4 py-5 sm:px-6"><header><h1 className="text-xl font-semibold">采购管理</h1><p className="mt-1 text-sm text-[#636366]">统一处理生产缺料、安全库存补货、采购下单和供应商到货。</p></header>{notice && <button onClick={() => setNotice(null)} className={`block w-full border px-4 py-3 text-left text-sm ${notice.error ? "border-[#FFB3B0] bg-[#FFF0F0] text-[#D70015]" : "border-[#A9D8B0] bg-[#F1FAF2] text-[#248A3D]"}`}>{notice.message}</button>}<nav className="flex border border-[#D1D1D6] bg-white"><Tab active={tab === "requirements"} onClick={() => setTab("requirements")}>采购需求池</Tab><Tab active={tab === "orders"} onClick={() => setTab("orders")}>采购订单与到货</Tab></nav>{tab === "requirements" ? <SupplyRequirements notify={notify} /> : <PurchasingCenter notify={notify} />}</main></div>;
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) { return <button onClick={onClick} className={`h-11 min-w-36 border-r border-[#E5E5EA] px-5 text-sm ${active ? "bg-[#007AFF] text-white" : "bg-white hover:bg-[#F7F7F9]"}`}>{children}</button>; }
