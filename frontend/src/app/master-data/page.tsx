"use client";

import { useState } from "react";
import MasterDataWorkspace from "@/components/inventory/MasterDataWorkspace";

export default function MasterDataPage() {
  const [notice, setNotice] = useState<{ message: string; error: boolean } | null>(null);
  const notify = (message: string, error = false) => setNotice({ message, error });
  return <div className="min-h-screen bg-[#F2F2F7] text-[#1C1C1E]"><main className="mx-auto max-w-[1680px] space-y-4 px-4 py-5 sm:px-6"><header><h1 className="text-xl font-semibold">基础资料</h1><p className="mt-1 text-sm text-[#636366]">统一维护物料、商品、供应商及其供货关系。</p></header>{notice && <button onClick={() => setNotice(null)} className={`block w-full border px-4 py-3 text-left text-sm ${notice.error ? "border-[#FFB3B0] bg-[#FFF0F0] text-[#D70015]" : "border-[#A9D8B0] bg-[#F1FAF2] text-[#248A3D]"}`}>{notice.message}</button>}<MasterDataWorkspace notify={notify} /></main></div>;
}
