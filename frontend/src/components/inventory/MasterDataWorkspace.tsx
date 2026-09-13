"use client";

import { useState } from "react";
import MaterialCatalog from "./MaterialCatalog";
import SupplierCatalog from "./SupplierCatalog";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";

export default function MasterDataWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"materials" | "suppliers">("materials");
  return <div className="space-y-4"><WorkspaceTabs items={[{ key: "materials", label: "物料与商品" }, { key: "suppliers", label: "供应商及供货" }] as const} value={tab} onChange={setTab} ariaLabel="基础资料视图" />{tab === "materials" ? <MaterialCatalog notify={notify}/> : <SupplierCatalog notify={notify}/>}</div>;
}
