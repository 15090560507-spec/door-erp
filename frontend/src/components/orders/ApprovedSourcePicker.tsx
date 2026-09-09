import { FileCheck2, Keyboard, Search } from "lucide-react";
import EmptyState from "@/components/workspace/EmptyState";
import LoadingPanel from "@/components/workspace/LoadingPanel";
import StatusChip from "@/components/workspace/StatusChip";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import type { SalesOrderCandidate } from "@/lib/salesOrderTypes";

export default function ApprovedSourcePicker({ open, candidates, loading, query, picked, establishedCustomer, onQueryChange, onSearch, onToggle, onAdd, onManual, onClose }: {
  open: boolean;
  candidates: SalesOrderCandidate[];
  loading: boolean;
  query: string;
  picked: Set<string>;
  establishedCustomer: string;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  onToggle: (candidate: SalesOrderCandidate) => void;
  onAdd: () => void;
  onManual: () => void;
  onClose: () => void;
}) {
  return (
    <ViewportDialog
      open={open}
      size="wide"
      title="关联已终审图纸及对应报价单"
      description={establishedCustomer ? `当前订单客户：${establishedCustomer}。只能继续选择该客户的图纸。` : "先选择一张图纸确定客户，随后可批量选择同一客户的其他图纸。"}
      onClose={onClose}
      footer={<><button type="button" className="ui-button ui-button--quiet" onClick={onManual}><Keyboard size={15} />手工录入</button><span className="source-picker__selection">已选 {picked.size} 项</span><button type="button" className="ui-button ui-button--secondary" onClick={onClose}>取消</button><button type="button" className="ui-button ui-button--primary" disabled={!picked.size} onClick={onAdd}>加入订单</button></>}
    >
      <div className="source-picker">
        <div className="source-picker__search"><label><Search size={16} aria-hidden="true" /><input value={query} onChange={(event) => onQueryChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") onSearch(); }} placeholder="客户、项目、门型、图纸编号" /></label><button type="button" className="ui-button ui-button--secondary" onClick={onSearch}>搜索</button></div>
        {loading ? <LoadingPanel rows={5} label="正在加载候选图纸" /> : candidates.length ? <div className="source-picker__list">{candidates.map((candidate) => {
          const incompatible = Boolean(establishedCustomer && candidate.customer_name !== establishedCustomer && !picked.has(candidate.task_id));
          const latestQuote = candidate.quotes[0];
          return <label key={candidate.task_id} className={`source-picker__item${picked.has(candidate.task_id) ? " is-selected" : ""}${incompatible ? " is-disabled" : ""}`}><input type="checkbox" checked={picked.has(candidate.task_id)} disabled={incompatible} onChange={() => onToggle(candidate)} /><span className="source-picker__main"><span className="source-picker__title"><strong>{candidate.customer_name}</strong><span>{candidate.product_name || candidate.door_type}</span></span><span className="source-picker__meta">{candidate.project_name || "未填项目"} · {candidate.door_type || "未填门型"} · {candidate.width} × {candidate.height} mm</span><span className="source-picker__trace">图纸 {candidate.task_id} · 终审 {candidate.approved_at || "未记录时间"}</span></span><span className="source-picker__state"><StatusChip tone="green"><FileCheck2 size={12} />已终审</StatusChip>{latestQuote ? <><StatusChip tone="blue">{candidate.quotes.length} 个报价</StatusChip><strong>¥{latestQuote.amount.toLocaleString()}</strong></> : <StatusChip tone="amber">暂无报价</StatusChip>}</span></label>;
        })}</div> : <EmptyState title="没有符合条件的终审图纸" description="调整关键词后搜索，或改用手工录入。" />}
      </div>
    </ViewportDialog>
  );
}
