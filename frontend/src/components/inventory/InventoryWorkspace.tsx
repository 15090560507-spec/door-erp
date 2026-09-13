"use client";

import { useState } from "react";
import InventoryOverview from "./InventoryOverview";
import InventoryTransactions from "./InventoryTransactions";
import InventoryTransferWorkbench from "./InventoryTransferWorkbench";
import MaterialIssueWorkbench from "./MaterialIssueWorkbench";
import ReceivingWorkbench from "./ReceivingWorkbench";
import SubcontractWorkbench from "./SubcontractWorkbench";
import WorkspaceTabs from "@/components/workspace/WorkspaceTabs";

export default function InventoryWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"issue" | "receiving" | "transfer" | "subcontract" | "overview" | "transactions">("issue");
  const tabs = [{ key: "issue", label: "领料与退料" }, { key: "receiving", label: "采购待检" }, { key: "transfer", label: "调拨与报废" }, { key: "subcontract", label: "外协作业" }, { key: "overview", label: "库存总览" }, { key: "transactions", label: "库存流水" }] as const;
  return <div className="space-y-4"><WorkspaceTabs items={tabs} value={tab} onChange={setTab} ariaLabel="库存管理视图" />{tab === "issue" ? <MaterialIssueWorkbench notify={notify} /> : tab === "receiving" ? <ReceivingWorkbench notify={notify} /> : tab === "transfer" ? <InventoryTransferWorkbench notify={notify} /> : tab === "subcontract" ? <SubcontractWorkbench notify={notify} /> : tab === "overview" ? <InventoryOverview notify={notify} /> : <InventoryTransactions notify={notify} />}</div>;
}
