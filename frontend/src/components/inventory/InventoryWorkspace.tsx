"use client";

import { useState } from "react";
import InventoryOverview from "./InventoryOverview";
import InventoryTransactions from "./InventoryTransactions";
import InventoryTransferWorkbench from "./InventoryTransferWorkbench";
import MaterialIssueWorkbench from "./MaterialIssueWorkbench";
import ReceivingWorkbench from "./ReceivingWorkbench";
import SubcontractWorkbench from "./SubcontractWorkbench";

export default function InventoryWorkspace({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<"issue" | "receiving" | "transfer" | "subcontract" | "overview" | "transactions">("issue");
  const tabs = [["issue", "领料与退料"], ["receiving", "采购待检"], ["transfer", "调拨与报废"], ["subcontract", "外协作业"], ["overview", "库存总览"], ["transactions", "库存流水"]] as const;
  return <div className="space-y-4"><div className="workspace-tabs flex overflow-x-auto">{tabs.map(([key, label]) => <button key={key} onClick={() => setTab(key)} className={`h-10 min-w-28 shrink-0 px-4 text-sm ${tab === key ? "bg-[#1B1B1F] text-white" : "bg-white text-[#5E5E67] hover:bg-[#F1F1F4]"}`}>{label}</button>)}</div>{tab === "issue" ? <MaterialIssueWorkbench notify={notify} /> : tab === "receiving" ? <ReceivingWorkbench notify={notify} /> : tab === "transfer" ? <InventoryTransferWorkbench notify={notify} /> : tab === "subcontract" ? <SubcontractWorkbench notify={notify} /> : tab === "overview" ? <InventoryOverview notify={notify} /> : <InventoryTransactions notify={notify} />}</div>;
}
