"use client";

import { useState } from "react";
import { FileUp } from "lucide-react";
import MaterialCatalog from "./MaterialCatalog";
import SupplierCatalog from "./SupplierCatalog";
import BomRuleCatalog from "./BomRuleCatalog";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";
import MasterDataImportDialog from "./MasterDataImportDialog";

export default function MasterDataWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"materials" | "suppliers" | "bom-rules">("materials");
  const [importOpen, setImportOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  return <div className="space-y-4"><div className="flex flex-wrap items-center gap-3"><WorkspaceTabs items={[{ key: "materials", label: "物料与商品" }, { key: "suppliers", label: "供应商及供货" }, { key: "bom-rules", label: "BOM 规则模板" }] as const} value={tab} onChange={setTab} ariaLabel="基础资料视图" /><button type="button" className="ui-button ui-button--primary ml-auto" onClick={() => setImportOpen(true)}><FileUp size={15}/>外部 ERP 导入</button></div><div key={refreshKey}>{tab === "materials" ? <MaterialCatalog notify={notify}/> : tab === "suppliers" ? <SupplierCatalog notify={notify}/> : <BomRuleCatalog notify={notify} />}</div><MasterDataImportDialog open={importOpen} onClose={() => setImportOpen(false)} onImported={() => setRefreshKey((value) => value + 1)} notify={notify}/></div>;
}
