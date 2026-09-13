"use client";

import { useState } from "react";
import MaterialCatalog from "./MaterialCatalog";
import SupplierCatalog from "./SupplierCatalog";
import BomRuleCatalog from "./BomRuleCatalog";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";

export default function MasterDataWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"materials" | "suppliers" | "bom-rules">("materials");
  return <div className="space-y-4"><WorkspaceTabs items={[{ key: "materials", label: "物料与商品" }, { key: "suppliers", label: "供应商及供货" }, { key: "bom-rules", label: "BOM 规则模板" }] as const} value={tab} onChange={setTab} ariaLabel="基础资料视图" />{tab === "materials" ? <MaterialCatalog notify={notify}/> : tab === "suppliers" ? <SupplierCatalog notify={notify}/> : <BomRuleCatalog notify={notify} />}</div>;
}
