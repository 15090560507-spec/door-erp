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
  return <div className="space-y-4"><div className="flex overflow-x-auto border border-[#D1D1D6] bg-white">{tabs.map(([key, label]) => <button key={key} onClick={() => setTab(key)} className={`h-10 min-w-28 shrink-0 border-r border-[#E5E5EA] px-4 text-sm ${tab === key ? "bg-[#007AFF] text-white" : "bg-white"}`}>{label}</button>)}</div>{tab === "issue" ? <MaterialIssueWorkbench notify={notify} /> : tab === "receiving" ? <ReceivingWorkbench notify={notify} /> : tab === "transfer" ? <InventoryTransferWorkbench notify={notify} /> : tab === "subcontract" ? <SubcontractWorkbench notify={notify} /> : tab === "overview" ? <InventoryOverview notify={notify} /> : <InventoryTransactions notify={notify} />}</div>;
}
