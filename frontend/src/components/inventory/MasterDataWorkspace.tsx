"use client";

import { useState } from "react";
import MaterialCatalog from "./MaterialCatalog";
import WarehouseSettings from "./WarehouseSettings";

export default function MasterDataWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"materials" | "warehouses">("materials");
  return <div className="space-y-4"><div className="flex border border-[#D1D1D6] bg-white"><button onClick={() => setTab("materials")} className={`h-10 min-w-28 border-r border-[#E5E5EA] px-4 text-sm ${tab === "materials" ? "bg-[#007AFF] text-white" : "bg-white"}`}>物料档案</button><button onClick={() => setTab("warehouses")} className={`h-10 min-w-28 px-4 text-sm ${tab === "warehouses" ? "bg-[#007AFF] text-white" : "bg-white"}`}>仓库设置</button></div>{tab === "materials" ? <MaterialCatalog notify={notify}/> : <WarehouseSettings notify={notify}/>}</div>;
}
