"use client";

import { useState } from "react";
import InventoryOverview from "./InventoryOverview";
import InventoryTransactions from "./InventoryTransactions";

export default function InventoryWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"overview" | "transactions">("overview");
  return <div className="space-y-4"><div className="flex border border-[#D1D1D6] bg-white"><button onClick={() => setTab("overview")} className={`h-10 min-w-28 border-r border-[#E5E5EA] px-4 text-sm ${tab === "overview" ? "bg-[#007AFF] text-white" : "bg-white"}`}>库存总览</button><button onClick={() => setTab("transactions")} className={`h-10 min-w-28 px-4 text-sm ${tab === "transactions" ? "bg-[#007AFF] text-white" : "bg-white"}`}>库存流水</button></div>{tab === "overview" ? <InventoryOverview notify={notify}/> : <InventoryTransactions notify={notify}/>}</div>;
}
