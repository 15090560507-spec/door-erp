"use client";

import { useState } from "react";
import MaterialCatalog from "./MaterialCatalog";
import SupplierCatalog from "./SupplierCatalog";

export default function MasterDataWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"materials" | "suppliers">("materials");
  return <div className="space-y-4"><div className="flex border border-[#D1D1D6] bg-white"><button onClick={() => setTab("materials")} className={`h-10 min-w-32 border-r border-[#E5E5EA] px-4 text-sm ${tab === "materials" ? "bg-[#007AFF] text-white" : "bg-white"}`}>物料与商品</button><button onClick={() => setTab("suppliers")} className={`h-10 min-w-36 px-4 text-sm ${tab === "suppliers" ? "bg-[#007AFF] text-white" : "bg-white"}`}>供应商及供货</button></div>{tab === "materials" ? <MaterialCatalog notify={notify}/> : <SupplierCatalog notify={notify}/>}</div>;
}
