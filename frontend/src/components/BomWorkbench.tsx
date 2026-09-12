"use client";

import {
  AlertTriangle,
  Boxes,
  CheckCheck,
  ClipboardList,
  FileClock,
  PackageCheck,
  Play,
  RefreshCw,
  Save,
  Search,
  Send,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/workspace/EmptyState";
import FilterBar from "@/components/workspace/FilterBar";
import InlineError from "@/components/workspace/InlineError";
import MasterDetail from "@/components/workspace/MasterDetail";
import MetricStrip from "@/components/workspace/MetricStrip";
import StatusChip from "@/components/workspace/StatusChip";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import WorkspaceHeader from "@/components/workspace/WorkspaceHeader";
import {
  createDoorBomVersion,
  generateDoorBom,
  getBomWorkbench,
  getDoorBom,
  publishDoorBom,
  saveDoorBomDraft,
  verifyDoorBomRows,
} from "@/lib/bomApi";
import type { BomDetail, BomDraftItem, BomRow, BomWorkbenchItem, BomWorkbenchState, BomWorkbenchSummary } from "@/lib/bomTypes";
import { getInventoryMaterials } from "@/lib/inventoryApi";
import type { InventoryMaterial } from "@/lib/inventoryTypes";

const emptySummary: BomWorkbenchSummary = {
  total: 0, pending_generation: 0, pending_verification: 0, missing_data: 0,
  shortage: 0, published: 0, changed: 0,
};

function apiMessage(error: unknown, fallback: string) {
  if (typeof error === "object" && error && "userMessage" in error) {
    return String((error as { userMessage?: string }).userMessage || fallback);
  }
  return error instanceof Error ? error.message : fallback;
}

function asDraftItem(row: BomRow): BomDraftItem {
  return {
    id: row.id, material_id: row.material_id, name: row.name, category: row.category,
    specification: row.specification, theoretical_quantity: Number(row.theoretical_quantity || 0),
    waste_rate: Number(row.waste_rate || 0), planned_quantity: Number(row.planned_quantity || 0),
    quantity: Number(row.quantity || 0), unit: row.unit, acquisition_method: row.acquisition_method,
    group_code: row.group_code, operation_code: row.operation_code, supplier_id: row.supplier_id,
    required_date: row.required_date || "", remark: row.remark || "",
  };
}

export default function BomWorkbench() {
  const [items, setItems] = useState<BomWorkbenchItem[]>([]);
  const [summary, setSummary] = useState(emptySummary);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [selectedDoorId, setSelectedDoorId] = useState<number | null>(null);
  const [detail, setDetail] = useState<BomDetail | null>(null);
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [publishOpen, setPublishOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [versionReason, setVersionReason] = useState("");
  const [notice, setNotice] = useState<{ title: string; message: string; error?: boolean } | null>(null);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const result = await getBomWorkbench({ q: query, status, page_size: 100 });
      setItems(result.items);
      setSummary(result.summary);
      setSelectedDoorId((current) => result.items.some((item) => item.door_unit_id === current)
        ? current : result.items[0]?.door_unit_id || null);
      setError("");
    } catch (requestError) {
      setError(apiMessage(requestError, "整单 BOM 列表加载失败"));
    } finally {
      setLoadingList(false);
    }
  }, [query, status]);

  const loadDetail = useCallback(async (doorId: number, version?: number) => {
    setLoadingDetail(true);
    try {
      setDetail(await getDoorBom(doorId, version));
      setSelectedRows(new Set());
      setError("");
    } catch (requestError) {
      setDetail(null);
      setError(apiMessage(requestError, "BOM 详情加载失败"));
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadList(); }, 180);
    return () => window.clearTimeout(timer);
  }, [loadList]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (selectedDoorId) void loadDetail(selectedDoorId);
      else setDetail(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadDetail, selectedDoorId]);

  useEffect(() => {
    getInventoryMaterials().then(setMaterials).catch(() => setMaterials([]));
  }, []);

  const orders = useMemo(() => {
    const groups = new Map<number, { orderId: number; orderNo: string; customer: string; project: string; doors: BomWorkbenchItem[] }>();
    items.forEach((item) => {
      const group = groups.get(item.order_id) || { orderId: item.order_id, orderNo: item.order_no, customer: item.customer, project: item.project, doors: [] };
      group.doors.push(item);
      groups.set(item.order_id, group);
    });
    return Array.from(groups.values());
  }, [items]);

  const editable = detail?.status === "草稿";
  const unresolved = detail?.rows.filter((row) => {
    const materialReady = row.match_status === "无需物料" || (row.match_status === "已匹配" && Boolean(row.material_id));
    return !materialReady || row.planned_quantity <= 0 || row.verification_status !== "已核验";
  }).length || 0;
  const selectedVerifiable = detail?.rows.filter((row) => selectedRows.has(row.id) && row.material_id && row.planned_quantity > 0 && row.verification_status !== "已核验") || [];
  const rowsById = useMemo(() => new Map((detail?.rows || []).map((row) => [row.id, row])), [detail?.rows]);

  const runAction = async (action: () => Promise<{ bom: BomDetail; message?: string }>, fallback: string) => {
    setBusy(true);
    try {
      const result = await action();
      setDetail(result.bom);
      setSelectedRows(new Set());
      setNotice({ title: "操作完成", message: result.message || fallback });
      await loadList();
    } catch (requestError) {
      setNotice({ title: "操作未完成", message: apiMessage(requestError, fallback), error: true });
    } finally {
      setBusy(false);
    }
  };

  const updateRow = (rowId: number, changes: Partial<BomRow>) => {
    setDetail((current) => current ? {
      ...current,
      rows: current.rows.map((row) => row.id === rowId ? { ...row, ...changes, verification_status: "待核验" } : row),
    } : current);
  };

  const saveDraft = () => {
    if (!detail || !editable) return;
    void runAction(
      () => saveDoorBomDraft(detail.door_unit_id, { items: detail.rows.map(asDraftItem), product_summary: detail.product_summary, special_requirements: detail.special_requirements }),
      "BOM 草稿保存失败",
    );
  };

  const verifySelected = () => {
    if (!detail || !selectedVerifiable.length) return;
    const doorUnitId = detail.door_unit_id;
    const itemIds = selectedVerifiable.map((row) => row.id);
    const draftItems = detail.rows.map(asDraftItem);
    void runAction(async () => {
      await saveDoorBomDraft(doorUnitId, { items: draftItems, product_summary: detail.product_summary, special_requirements: detail.special_requirements });
      return verifyDoorBomRows(doorUnitId, itemIds);
    }, "BOM 核验失败");
  };

  const publish = () => {
    if (!detail) return;
    setPublishOpen(false);
    void runAction(() => publishDoorBom(detail.door_unit_id, "下料员确认发布"), "BOM 发布失败");
  };

  const createVersion = () => {
    if (!detail || !versionReason.trim()) return;
    setVersionOpen(false);
    void runAction(() => createDoorBomVersion(detail.door_unit_id, versionReason.trim()), "新版本创建失败");
    setVersionReason("");
  };

  return (
    <div className="min-h-screen bg-[#F5F5F7] text-[#1B1B1F]">
      <main className="workspace-page workspace-page--wide bom-workbench">
        <WorkspaceHeader
          title="整单 BOM 下料"
          description="按订单查看每樘门的材料清单；下料员补齐物料与数量、逐项核验后发布到采购、仓储和车间。"
          context={<><Boxes size={14} />经营管理 / 订单确认后</>}
          actions={<button type="button" className="ui-button ui-button--secondary" disabled={busy || loadingList} onClick={() => void loadList()}><RefreshCw size={15} />刷新</button>}
        />

        <MetricStrip items={[
          { key: "all", label: "门樘总数", value: summary.total, icon: <ClipboardList size={16} />, active: status === "", onClick: () => setStatus("") },
          { key: "generate", label: "待生成", value: summary.pending_generation, tone: "blue", icon: <Play size={16} />, active: status === "待生成", onClick: () => setStatus("待生成") },
          { key: "verify", label: "待核验", value: summary.pending_verification, tone: "amber", icon: <CheckCheck size={16} />, active: status === "待核验", onClick: () => setStatus("待核验") },
          { key: "missing", label: "缺少资料", value: summary.missing_data, tone: "red", icon: <AlertTriangle size={16} />, active: status === "缺少资料", onClick: () => setStatus("缺少资料") },
          { key: "published", label: "已发布", value: summary.published, tone: "green", icon: <PackageCheck size={16} />, active: status === "已发布", onClick: () => setStatus("已发布") },
        ]} />

        <FilterBar summary={`当前 ${items.length} 樘`}>
          <label className="bom-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="订单号、生产编号、客户、项目" /></label>
          <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="BOM 状态">
            <option value="">全部状态</option>
            {(["待生成", "待核验", "缺少资料", "缺料", "已发布", "已变更"] as BomWorkbenchState[]).map((value) => <option key={value}>{value}</option>)}
          </select>
        </FilterBar>

        {error && <InlineError message={error} onRetry={() => void loadList()} />}

        <MasterDetail
          className="bom-master-detail"
          listWidth={380}
          list={<div className="bom-tree">
            <div className="bom-panel-title"><span>订单与门樘</span><small>{orders.length} 张订单</small></div>
            {loadingList ? <div className="bom-list-loading">正在读取订单...</div> : orders.length ? orders.map((order) => (
              <section key={order.orderId} className="bom-order-group">
                <header><strong>{order.orderNo}</strong><span>{order.customer}</span><small>{order.project || "未填写项目"} · {order.doors.length} 樘</small></header>
                <div>{order.doors.map((door) => (
                  <button key={door.door_unit_id} type="button" className={selectedDoorId === door.door_unit_id ? "is-active" : ""} onClick={() => setSelectedDoorId(door.door_unit_id)}>
                    <span><strong>{door.production_no}</strong><small>{door.product_name} · {door.specification || "未填写规格"}</small></span>
                    <span className="bom-tree__states">{door.states.slice(0, 2).map((state) => <StatusChip key={state}>{state}</StatusChip>)}</span>
                  </button>
                ))}</div>
              </section>
            )) : <EmptyState compact title="没有符合条件的门樘" description="请调整筛选条件，或先在订单确认中生成门樘。" />}
          </div>}
          detail={loadingDetail ? <div className="bom-detail-loading">正在读取 BOM 明细...</div> : detail ? (
            <div className="bom-detail">
              <header className="bom-detail__header">
                <div><span className="bom-detail__eyebrow">{detail.order_no} / {detail.customer}</span><h2>{detail.production_no}</h2><p>{detail.product_name} · {detail.specification || "未填写规格"} · 交期 {detail.due_date || "未设置"}</p></div>
                <div className="bom-detail__status"><StatusChip tone={detail.status === "已确认" ? "green" : "blue"}>{detail.status === "已确认" ? "已发布" : "草稿"}</StatusChip><strong>V{detail.version}</strong></div>
              </header>

              <div className="bom-actionbar">
                <div><span>共 {detail.rows.length} 项</span><span>待处理 {unresolved} 项</span><span>规则 {detail.rule_version || "未生成"}</span></div>
                <div>
                  <button type="button" className="ui-button ui-button--secondary" disabled={busy || !editable} onClick={() => void runAction(() => generateDoorBom(detail.door_unit_id), "BOM 生成失败")}><Play size={15} />{detail.rows.length ? "重新生成" : "生成 BOM"}</button>
                  <button type="button" className="ui-button ui-button--secondary" disabled={busy || !editable} onClick={saveDraft}><Save size={15} />保存草稿</button>
                  <button type="button" className="ui-button ui-button--secondary" disabled={busy || !editable || !selectedVerifiable.length} onClick={verifySelected}><CheckCheck size={15} />核验选中</button>
                  {detail.status === "已确认" ? <button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={() => setVersionOpen(true)}><FileClock size={15} />新建版本</button> : <button type="button" className="ui-button ui-button--primary" disabled={busy || unresolved > 0 || !detail.rows.length} onClick={() => setPublishOpen(true)}><Send size={15} />发布 BOM</button>}
                </div>
              </div>

              {detail.warnings.length > 0 && <section className="bom-warnings"><strong><AlertTriangle size={16} />生成提示 {detail.warnings.length} 项</strong><div>{detail.warnings.slice(0, 5).map((warning) => <p key={warning.id}><span>{warning.blocking ? "阻断" : "提示"}</span>{warning.message}</p>)}</div></section>}

              <div className="bom-table-wrap">
                <table className="bom-table">
                  <thead><tr><th className="bom-check"><input type="checkbox" aria-label="全选当前可核验项" checked={Boolean(selectedVerifiable.length) && selectedVerifiable.length === detail.rows.filter((row) => row.material_id && row.planned_quantity > 0 && row.verification_status !== "已核验").length} onChange={(event) => setSelectedRows(event.target.checked ? new Set(detail.rows.filter((row) => row.material_id && row.planned_quantity > 0 && row.verification_status !== "已核验").map((row) => row.id)) : new Set())} /></th><th>部件/物料</th><th>规格</th><th>物料档案</th><th>理论量</th><th>损耗%</th><th>计划量</th><th>单位</th><th>取得方式</th><th>核验</th></tr></thead>
                  <tbody>{detail.groups.map((group) => {
                    const groupRows = group.rows.map((row) => rowsById.get(row.id)).filter((row): row is BomRow => Boolean(row));
                    return [<tr className="bom-group-row" key={`${group.code}-title`}><td colSpan={10}>{group.label}<span>{groupRows.length} 项</span></td></tr>, ...groupRows.map((row) => (
                      <tr key={row.id} className={row.verification_status === "已核验" ? "is-verified" : ""}>
                        <td className="bom-check"><input type="checkbox" aria-label={`选择 ${row.name}`} disabled={!editable || row.verification_status === "已核验"} checked={selectedRows.has(row.id)} onChange={(event) => setSelectedRows((current) => { const next = new Set(current); if (event.target.checked) next.add(row.id); else next.delete(row.id); return next; })} /></td>
                        <td><strong>{row.name}</strong><small>{row.operation_code || row.category}</small></td>
                        <td><input disabled={!editable} value={row.specification || ""} onChange={(event) => updateRow(row.id, { specification: event.target.value })} /></td>
                        <td><select disabled={!editable} value={row.material_id || ""} onChange={(event) => { const material = materials.find((item) => item.id === Number(event.target.value)); updateRow(row.id, { material_id: material?.id || null, material_code: material?.code || null, material_name: material?.name || null, unit: material?.unit || row.unit }); }}><option value="">待匹配</option>{materials.map((material) => <option key={material.id} value={material.id}>{material.code} · {material.name}</option>)}</select><small className={row.material_id ? "is-ok" : "is-alert"}>{row.material_id ? row.material_name : row.match_status}</small></td>
                        <td className="bom-number">{Number(row.theoretical_quantity || 0).toLocaleString()}</td>
                        <td><input className="bom-number-input" type="number" min="0" max="100" step="0.1" disabled={!editable} value={row.waste_rate} onChange={(event) => updateRow(row.id, { waste_rate: Number(event.target.value) })} /></td>
                        <td><input className="bom-number-input" type="number" min="0" step="0.001" disabled={!editable} value={row.planned_quantity} onChange={(event) => updateRow(row.id, { planned_quantity: Number(event.target.value), quantity: Number(event.target.value) })} /></td>
                        <td><input className="bom-unit-input" disabled={!editable} value={row.unit || ""} onChange={(event) => updateRow(row.id, { unit: event.target.value })} /></td>
                        <td><select disabled={!editable} value={row.acquisition_method || "待确定"} onChange={(event) => updateRow(row.id, { acquisition_method: event.target.value })}><option>待确定</option><option>库存领料</option><option>采购</option><option>内部加工</option><option>外协加工</option></select></td>
                        <td><StatusChip tone={row.verification_status === "已核验" ? "green" : row.material_id ? "amber" : "red"}>{row.verification_status}</StatusChip></td>
                      </tr>
                    ))];
                  })}</tbody>
                </table>
              </div>

              <footer className="bom-detail__footer"><span>发布后自动产生物料需求，并进入采购、仓储和车间工作包。</span><div className="bom-version-list"><span>版本：</span>{detail.version_history.map((version) => <button type="button" key={version.version} className={version.version === detail.version ? "is-current" : ""} onClick={() => void loadDetail(detail.door_unit_id, version.version)}>V{version.version}</button>)}</div></footer>
            </div>
          ) : <EmptyState title="选择门樘查看整单 BOM" description="左侧按订单归集，每樘门保持独立生产编号、BOM 和核验记录。" />}
          listLabel="订单与门樘树"
          detailLabel="整单 BOM 明细"
        />
      </main>

      <ViewportDialog open={publishOpen} title="发布当前 BOM？" description="发布后当前版本将冻结，并自动产生下游物料需求。" size="small" onClose={() => setPublishOpen(false)} footer={<><button type="button" className="ui-button ui-button--secondary" onClick={() => setPublishOpen(false)}>返回检查</button><button type="button" className="ui-button ui-button--primary" onClick={publish}><Send size={15} />确认发布</button></>}><p className="bom-dialog-copy">当前 V{detail?.version} 共 {detail?.rows.length || 0} 项，全部物料、计划数量和核验状态已经通过。</p></ViewportDialog>
      <ViewportDialog open={versionOpen} title="新建 BOM 版本" description="已发布版本保持不变，新版本用于记录生产变更。" size="small" onClose={() => setVersionOpen(false)} footer={<><button type="button" className="ui-button ui-button--secondary" onClick={() => setVersionOpen(false)}>取消</button><button type="button" className="ui-button ui-button--primary" disabled={!versionReason.trim()} onClick={createVersion}>创建版本</button></>}><label className="bom-dialog-field"><span>变更原因 *</span><textarea rows={4} value={versionReason} onChange={(event) => setVersionReason(event.target.value)} placeholder="例如：客户调整门板材质" /></label></ViewportDialog>
      <ViewportDialog open={Boolean(notice)} title={notice?.title || "提示"} size="small" onClose={() => setNotice(null)} footer={<button type="button" className="ui-button ui-button--primary" onClick={() => setNotice(null)}>知道了</button>}><p className={notice?.error ? "bom-dialog-copy is-error" : "bom-dialog-copy"}>{notice?.message}</p></ViewportDialog>
      {busy && <div className="fixed inset-0 z-[190] cursor-wait bg-black/[0.025]" aria-hidden="true" />}
    </div>
  );
}
