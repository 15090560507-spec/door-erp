"use client";

import { useState } from "react";
import InventoryWorkspace from "@/components/inventory/InventoryWorkspace";
import WarehouseSettings from "@/components/inventory/WarehouseSettings";

export default function InventoryPage() {
  const [settings, setSettings] = useState(false);
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const notify = (message: string, error = false) => setNotice({ message, error });
  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]"><main className="workspace-page workspace-page--wide space-y-4"><header className="flex items-end gap-3"><div className="flex-1"><h1 className="text-xl font-semibold">库存管理</h1><p className="mt-1 text-sm text-[#636366]">全厂共享库存，统一收货待检、领退料、调拨报废和库存流水。</p></div><button onClick={() => setSettings((value) => !value)} className="h-9 border border-[#C7C7CC] bg-white px-4 text-sm">{settings ? "返回库存业务" : "仓库与库位设置"}</button></header>{notice && <button onClick={() => setNotice(null)} className={`block w-full border px-4 py-3 text-left text-sm ${notice.error ? "border-[#FFB3B0] bg-[#FFF0F0] text-[#D70015]" : "border-[#A9D8B0] bg-[#F1FAF2] text-[#248A3D]"}`}>{notice.message}</button>}{settings ? <WarehouseSettings notify={notify} /> : <InventoryWorkspace notify={notify} />}</main></div>;
}
