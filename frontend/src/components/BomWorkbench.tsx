"use client";

import {
  AlertTriangle,
  Boxes,
  CheckCheck,
  ClipboardList,
  Copy,
  Database,
  FileClock,
  PackageCheck,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  Send,
  Trash2,
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
import { apiErrorMessage } from "@/lib/api";
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
import { createInventoryMaterial, getInventoryMaterials } from "@/lib/inventoryApi";
import type { InventoryMaterial, MaterialPayload } from "@/lib/inventoryTypes";

const emptySummary: BomWorkbenchSummary = {
  total: 0, pending_generation: 0, pending_verification: 0, missing_data: 0,
  shortage: 0, published: 0, changed: 0,
};

const BOM_GROUP_OPTIONS = [
  ["frame", "门框与门槛"], ["panel", "门扇与面板"], ["skeleton", "骨架与型材"],
  ["trim", "门套/门头/门柱"], ["glass", "玻璃与线条"], ["hardware", "五金与开启机构"],
  ["ornament", "花件与外购装饰"], ["consumable", "辅料与耗材"], ["packaging", "包装"],
  ["subcontract", "外协加工"], ["other", "其他"],
] as const;

function asDraftItem(row: BomRow): BomDraftItem {
  return {
    id: row.id > 0 ? row.id : undefined, parent_id: row.parent_id, material_id: row.material_id, name: row.name, category: row.category,
    specification: row.specification, theoretical_quantity: Number(row.theoretical_quantity || 0),
    waste_rate: Number(row.waste_rate || 0), planned_quantity: Number(row.planned_quantity || 0),
    quantity: Number(row.quantity || 0), unit: row.unit, acquisition_method: row.acquisition_method,
    group_code: row.group_code, operation_code: row.operation_code, supplier_id: row.supplier_id,
    required_date: row.required_date || "", remark: row.remark || "",
    item_kind: row.item_kind || "material", procurement_mode: row.procurement_mode || "stock",
    drawing_parameters: row.drawing_parameters || {},
  };
}

let nextTemporaryRowId = -1;

function newBomRow(source?: BomRow, group?: { code: string; label: string }): BomRow {
  const selfMade = source?.procurement_mode === "make" || ["assembly", "manufactured_part"].includes(source?.item_kind || "");
  return {
    id: nextTemporaryRowId--,
    parent_id: null,
    material_id: source?.material_id || null,
    material_code: source?.material_code || null,
    material_name: source?.material_name || null,
    material_specification: source?.material_specification || null,
    material_unit: source?.material_unit || null,
    supplier_id: source?.supplier_id || null,
    supplier_name: source?.supplier_name || null,
    name: source ? `${source.name}（复制）` : "",
    category: source?.category || group?.label || "其他",
    specification: source?.specification || "",
    quantity: source?.quantity || 1,
    theoretical_quantity: source?.theoretical_quantity || 1,
    waste_rate: source?.waste_rate || 0,
    planned_quantity: source?.planned_quantity || 1,
    unit: source?.unit || "件",
    acquisition_method: source?.acquisition_method || "待确定",
    group_code: source?.group_code || group?.code || "other",
    operation_code: source?.operation_code || "MANUAL",
    required_date: source?.required_date || "",
    remark: source?.remark || "",
    match_status: selfMade ? "无需物料" : source?.material_id ? "已匹配" : "待匹配",
    verification_status: selfMade ? "已核验" : "待核验",
    source_type: "manual",
    item_kind: source?.item_kind || "material",
    procurement_mode: source?.procurement_mode || "stock",
    drawing_parameters: source?.drawing_parameters || {},
  };
}

type BomWorkbenchProps = {
  embedded?: boolean;
  initialDoorId?: number;
};

export default function BomWorkbench({ embedded = false, initialDoorId }: BomWorkbenchProps = {}) {
  const [items, setItems] = useState<BomWorkbenchItem[]>([]);
  const [summary, setSummary] = useState(emptySummary);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [selectedDoorId, setSelectedDoorId] = useState<number | null>(initialDoorId || null);
  const [detail, setDetail] = useState<BomDetail | null>(null);
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
  const [deletedRowIds, setDeletedRowIds] = useState<number[]>([]);
  const [materialRow, setMaterialRow] = useState<BomRow | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [publishOpen, setPublishOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addGroupCode, setAddGroupCode] = useState<string>("hardware");
  const [versionReason, setVersionReason] = useState("");
  const [notice, setNotice] = useState<{ title: string; message: string; error?: boolean } | null>(null);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const result = await getBomWorkbench({ q: query, status, page_size: 100 });
      setItems(result.items);
      setSummary(result.summary);
      setSelectedDoorId((current) => {
        const preferred = current || initialDoorId || null;
        return result.items.some((item) => item.door_unit_id === preferred)
          ? preferred : result.items[0]?.door_unit_id || null;
      });
      setError("");
    } catch (requestError) {
      setError(apiErrorMessage(requestError, "整单 BOM 列表加载失败"));
    } finally {
      setLoadingList(false);
    }
  }, [initialDoorId, query, status]);

  useEffect(() => {
    if (initialDoorId) setSelectedDoorId(initialDoorId);
  }, [initialDoorId]);

  const loadDetail = useCallback(async (doorId: number, version?: number) => {
    setLoadingDetail(true);
    try {
      setDetail(await getDoorBom(doorId, version));
      setSelectedRows(new Set());
      setDeletedRowIds([]);
      setError("");
    } catch (requestError) {
      setDetail(null);
      setError(apiErrorMessage(requestError, "BOM 详情加载失败"));
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
    const selfMade = row.procurement_mode === "make" || ["assembly", "manufactured_part"].includes(row.item_kind);
    const materialReady = selfMade || row.match_status === "无需物料" || (row.match_status === "已匹配" && Boolean(row.material_id));
    return !materialReady || row.planned_quantity <= 0 || row.verification_status !== "已核验";
  }).length || 0;
  const selectedVerifiable = detail?.rows.filter((row) => row.id > 0 && selectedRows.has(row.id) && row.procurement_mode !== "make" && row.material_id && row.planned_quantity > 0 && row.verification_status !== "已核验") || [];
  const rowsById = useMemo(() => new Map((detail?.rows || []).map((row) => [row.id, row])), [detail?.rows]);
  const displayGroups = useMemo(() => {
    if (!detail) return [];
    const labels = new Map<string, string>(BOM_GROUP_OPTIONS.map(([code, label]) => [code, label]));
    detail.groups.forEach((group) => labels.set(group.code, group.label));
    const codes = [...detail.groups.map((group) => group.code)];
    detail.rows.forEach((row) => { if (!codes.includes(row.group_code)) codes.push(row.group_code); });
    return codes.map((code) => {
      const rows = detail.rows.filter((row) => row.group_code === code);
      return { code, label: labels.get(code) || (code === "other" ? "其他与临时项" : code), count: rows.length, rows };
    }).filter((group) => group.rows.length);
  }, [detail]);

  const runAction = async (action: () => Promise<{ bom: BomDetail; message?: string }>, fallback: string) => {
    setBusy(true);
    try {
      const result = await action();
      setDetail(result.bom);
      setSelectedRows(new Set());
      setDeletedRowIds([]);
      setNotice({ title: "操作完成", message: result.message || fallback });
      await loadList();
    } catch (requestError) {
      setNotice({ title: "操作未完成", message: apiErrorMessage(requestError, fallback), error: true });
    } finally {
      setBusy(false);
    }
  };

  const updateRow = (rowId: number, changes: Partial<BomRow>) => {
    setDetail((current) => current ? {
      ...current,
      rows: current.rows.map((row) => {
        if (row.id !== rowId) return row;
        const next = { ...row, ...changes };
        const selfMade = next.procurement_mode === "make" || ["assembly", "manufactured_part"].includes(next.item_kind);
        return {
          ...next,
          material_id: selfMade ? null : next.material_id,
          match_status: selfMade ? "无需物料" : next.match_status,
          verification_status: selfMade ? "已核验" : "待核验",
        };
      }),
    } : current);
  };

  const addRow = (source?: BomRow, group?: { code: string; label: string }) => {
    setDetail((current) => current ? { ...current, rows: [...current.rows, newBomRow(source, group)] } : current);
  };

  const removeRow = (row: BomRow) => {
    setDetail((current) => current ? { ...current, rows: current.rows.filter((item) => item.id !== row.id) } : current);
    setSelectedRows((current) => { const next = new Set(current); next.delete(row.id); return next; });
    if (row.id > 0) setDeletedRowIds((current) => current.includes(row.id) ? current : [...current, row.id]);
  };

  const saveDraft = () => {
    if (!detail || !editable) return;
    void runAction(
      () => saveDoorBomDraft(detail.door_unit_id, { items: detail.rows.map(asDraftItem), delete_item_ids: deletedRowIds, product_summary: detail.product_summary, special_requirements: detail.special_requirements, frame_trim_mode: detail.frame_trim_mode }),
      "BOM 草稿保存失败",
    );
  };

  const applyFrameTrimMode = () => {
    if (!detail || !editable) return;
    const doorUnitId = detail.door_unit_id;
    void runAction(async () => {
      await saveDoorBomDraft(doorUnitId, { items: detail.rows.map(asDraftItem), delete_item_ids: deletedRowIds, product_summary: detail.product_summary, special_requirements: detail.special_requirements, frame_trim_mode: detail.frame_trim_mode });
      return generateDoorBom(doorUnitId);
    }, "门框门套制造方式应用失败");
  };

  const verifySelected = () => {
    if (!detail || !selectedVerifiable.length) return;
    const doorUnitId = detail.door_unit_id;
    const itemIds = selectedVerifiable.map((row) => row.id);
    const draftItems = detail.rows.map(asDraftItem);
    void runAction(async () => {
      await saveDoorBomDraft(doorUnitId, { items: draftItems, delete_item_ids: deletedRowIds, product_summary: detail.product_summary, special_requirements: detail.special_requirements, frame_trim_mode: detail.frame_trim_mode });
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
    <div className={embedded ? "bom-workbench-root is-embedded" : "min-h-screen bg-[#F5F5F7] text-[#1B1B1F]"}>
      <main className={embedded ? "bom-workbench bom-workbench--embedded" : "workspace-page workspace-page--wide bom-workbench"}>
        <WorkspaceHeader
          title="BOM与工艺准备"
          description="从订单确认结果生成整单 BOM、下料清单和工艺路线；发布后由生产工作包承接实际下料与加工。"
          context={<><Boxes size={14} />经营管理 / 生产准备</>}
          actions={<button type="button" className="ui-button ui-button--secondary" disabled={busy || loadingList} onClick={() => void loadList()}><RefreshCw size={15} />刷新</button>}
        />

        <section className="bom-stage-strip" aria-label="BOM与工艺准备业务阶段">
          <div><span>1</span><strong>BOM准备</strong><small>生成清单并补齐物料、规格与计划数量</small></div>
          <div><span>2</span><strong>核验发布</strong><small>逐项核验，发布后冻结当前版本</small></div>
          <div><span>3</span><strong>释放执行</strong><small>形成物料需求和工作包，交给采购、仓储与车间</small></div>
        </section>

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
                  <button type="button" className="ui-button ui-button--secondary" disabled={busy || !editable} onClick={() => setAddOpen(true)}><Plus size={15} />新增项目</button>
                  <button type="button" className="ui-button ui-button--secondary" disabled={busy || !editable} onClick={saveDraft}><Save size={15} />保存草稿</button>
                  <button type="button" className="ui-button ui-button--secondary" disabled={busy || !editable || !selectedVerifiable.length} onClick={verifySelected}><CheckCheck size={15} />核验选中</button>
                  {detail.status === "已确认" ? <button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={() => setVersionOpen(true)}><FileClock size={15} />新建版本</button> : <button type="button" className="ui-button ui-button--primary" disabled={busy || unresolved > 0 || !detail.rows.length} onClick={() => setPublishOpen(true)}><Send size={15} />发布 BOM</button>}
                </div>
              </div>

              <section className="bom-manufacturing-mode">
                <div><strong>门框/门套制造方式</strong><small>决定门框、门套外皮与骨架在 BOM 和生产进度中的组合方式</small></div>
                <select disabled={!editable} value={detail.frame_trim_mode || "separate"} onChange={(event) => setDetail({ ...detail, frame_trim_mode: event.target.value as BomDetail["frame_trim_mode"] })}>
                  <option value="separate">全部分体</option>
                  <option value="integrated_skeleton">骨架连体、外皮分体</option>
                  <option value="fully_integrated">骨架连体、外皮连体</option>
                </select>
                <button type="button" className="ui-button ui-button--secondary" disabled={busy || !editable} onClick={applyFrameTrimMode}><RefreshCw size={15} />应用并重新生成</button>
              </section>

              {detail.warnings.length > 0 && <section className="bom-warnings"><strong><AlertTriangle size={16} />生成提示 {detail.warnings.length} 项</strong><div>{detail.warnings.slice(0, 5).map((warning) => <p key={warning.id}><span>{warning.blocking ? "阻断" : "提示"}</span>{warning.message}</p>)}</div></section>}

              <div className="bom-table-wrap">
                <table className="bom-table">
                  <thead><tr><th className="bom-check"><input type="checkbox" aria-label="全选当前可核验项" checked={Boolean(selectedVerifiable.length) && selectedVerifiable.length === detail.rows.filter((row) => row.id > 0 && row.procurement_mode !== "make" && row.material_id && row.planned_quantity > 0 && row.verification_status !== "已核验").length} onChange={(event) => setSelectedRows(event.target.checked ? new Set(detail.rows.filter((row) => row.id > 0 && row.procurement_mode !== "make" && row.material_id && row.planned_quantity > 0 && row.verification_status !== "已核验").map((row) => row.id)) : new Set())} /></th><th>部件/物料</th><th>规格</th><th>物料档案</th><th>理论量</th><th>损耗%</th><th>计划量</th><th>单位</th><th>取得方式</th><th>核验</th><th>操作</th></tr></thead>
                  <tbody>{displayGroups.map((group) => {
                    const groupRows = group.rows.map((row) => rowsById.get(row.id)).filter((row): row is BomRow => Boolean(row));
                    return [<tr className="bom-group-row" key={`${group.code}-title`}><td colSpan={11}><div><span className="bom-group-row__label">{group.label}<small>{groupRows.length} 项</small></span>{editable && <button type="button" onClick={() => addRow(undefined, { code: group.code, label: group.label })}><Plus size={13} />新增本类项目</button>}</div></td></tr>, ...groupRows.map((row) => (
                      <tr key={row.id} className={row.verification_status === "已核验" ? "is-verified" : ""}>
                        <td className="bom-check"><input type="checkbox" aria-label={`选择 ${row.name}`} disabled={!editable || row.id < 0 || row.procurement_mode === "make" || row.verification_status === "已核验"} checked={selectedRows.has(row.id)} onChange={(event) => setSelectedRows((current) => { const next = new Set(current); if (event.target.checked) next.add(row.id); else next.delete(row.id); return next; })} /></td>
                        <td className={row.parent_id ? "bom-tree-cell is-child" : "bom-tree-cell"}><input disabled={!editable} value={row.name || ""} onChange={(event) => updateRow(row.id, { name: event.target.value })} /><small>{row.procurement_mode === "make" ? "按图自制" : row.source_type === "manual" ? "手工项目" : row.operation_code || row.category}</small></td>
                        <td><input disabled={!editable} value={row.specification || ""} onChange={(event) => updateRow(row.id, { specification: event.target.value })} /></td>
                        <td>{row.procurement_mode === "make" ? <div className="bom-self-made"><strong>无需建物料</strong><small>尺寸与参数保存在本单 BOM</small></div> : <><select disabled={!editable} value={row.material_id || ""} onChange={(event) => { const material = materials.find((item) => item.id === Number(event.target.value)); updateRow(row.id, { material_id: material?.id || null, material_code: material?.code || null, material_name: material?.name || null, unit: material?.unit || row.unit, match_status: material ? "已匹配" : "待匹配" }); }}><option value="">待匹配</option>{materials.map((material) => <option key={material.id} value={material.id}>{material.code} · {material.name}</option>)}</select><small className={row.material_id ? "is-ok" : "is-alert"}>{row.material_id ? row.material_name : row.match_status}</small></>}</td>
                        <td className="bom-number">{Number(row.theoretical_quantity || 0).toLocaleString()}</td>
                        <td><input className="bom-number-input" type="number" min="0" max="100" step="0.1" disabled={!editable} value={row.waste_rate} onChange={(event) => updateRow(row.id, { waste_rate: Number(event.target.value) })} /></td>
                        <td><input className="bom-number-input" type="number" min="0" step="0.001" disabled={!editable} value={row.planned_quantity} onChange={(event) => updateRow(row.id, { planned_quantity: Number(event.target.value), quantity: Number(event.target.value) })} /></td>
                        <td><input className="bom-unit-input" disabled={!editable} value={row.unit || ""} onChange={(event) => updateRow(row.id, { unit: event.target.value })} /></td>
                        <td><select disabled={!editable || row.procurement_mode === "make"} value={row.acquisition_method || "待确定"} onChange={(event) => updateRow(row.id, { acquisition_method: event.target.value })}>{row.procurement_mode === "make" && <option>按图自制</option>}<option>待确定</option><option>库存领料</option><option>采购</option><option>内部加工</option><option>外协加工</option></select></td>
                        <td><StatusChip tone={row.procurement_mode === "make" || row.verification_status === "已核验" ? "green" : row.material_id ? "amber" : "red"}>{row.procurement_mode === "make" ? "自制确认" : row.id < 0 ? "先保存" : row.verification_status}</StatusChip></td>
                        <td><div className="bom-row-actions">{row.procurement_mode !== "make" && !row.material_id && <button type="button" disabled={!editable} title="把临时项建立为物料档案" aria-label={`将${row.name || "临时项"}建立为物料档案`} onClick={() => setMaterialRow(row)}><Database size={14} /></button>}<button type="button" disabled={!editable} title="复制项目" aria-label={`复制${row.name || "项目"}`} onClick={() => addRow(row)}><Copy size={14} /></button><button type="button" disabled={!editable} title="删除项目" aria-label={`删除${row.name || "项目"}`} className="is-danger" onClick={() => removeRow(row)}><Trash2 size={14} /></button></div></td>
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

      {materialRow && <BomMaterialDialog row={materialRow} onClose={() => setMaterialRow(null)} onCreated={(material, message) => { setMaterials((current) => [...current.filter((item) => item.id !== material.id), material].sort((left, right) => left.code.localeCompare(right.code, "zh-CN"))); updateRow(materialRow.id, { material_id: material.id, material_code: material.code, material_name: material.name, material_specification: material.specification, material_unit: material.unit, unit: material.unit, match_status: "已匹配" }); setMaterialRow(null); setNotice({ title: "物料已建档", message }); }} />}
      <ViewportDialog open={addOpen} title="新增 BOM 项目" description="先选择归属分类，新项目会直接出现在该分类中。" size="small" onClose={() => setAddOpen(false)} footer={<><button type="button" className="ui-button ui-button--secondary" onClick={() => setAddOpen(false)}>取消</button><button type="button" className="ui-button ui-button--primary" onClick={() => { const group = BOM_GROUP_OPTIONS.find(([code]) => code === addGroupCode) || BOM_GROUP_OPTIONS[BOM_GROUP_OPTIONS.length - 1]; addRow(undefined, { code: group[0], label: group[1] }); setAddOpen(false); }}><Plus size={15}/>新增到该分类</button></>}><label className="bom-dialog-field"><span>归属分类</span><select value={addGroupCode} onChange={(event) => setAddGroupCode(event.target.value)}>{BOM_GROUP_OPTIONS.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select></label></ViewportDialog>
      <ViewportDialog open={publishOpen} title="发布当前 BOM？" description="发布后当前版本将冻结，并自动产生下游物料需求。" size="small" onClose={() => setPublishOpen(false)} footer={<><button type="button" className="ui-button ui-button--secondary" onClick={() => setPublishOpen(false)}>返回检查</button><button type="button" className="ui-button ui-button--primary" onClick={publish}><Send size={15} />确认发布</button></>}><p className="bom-dialog-copy">当前 V{detail?.version} 共 {detail?.rows.length || 0} 项，全部物料、计划数量和核验状态已经通过。</p></ViewportDialog>
      <ViewportDialog open={versionOpen} title="新建 BOM 版本" description="已发布版本保持不变，新版本用于记录生产变更。" size="small" onClose={() => setVersionOpen(false)} footer={<><button type="button" className="ui-button ui-button--secondary" onClick={() => setVersionOpen(false)}>取消</button><button type="button" className="ui-button ui-button--primary" disabled={!versionReason.trim()} onClick={createVersion}>创建版本</button></>}><label className="bom-dialog-field"><span>变更原因 *</span><textarea rows={4} value={versionReason} onChange={(event) => setVersionReason(event.target.value)} placeholder="例如：客户调整门板材质" /></label></ViewportDialog>
      <ViewportDialog open={Boolean(notice)} title={notice?.title || "提示"} size="small" onClose={() => setNotice(null)} footer={<button type="button" className="ui-button ui-button--primary" onClick={() => setNotice(null)}>知道了</button>}><p className={notice?.error ? "bom-dialog-copy is-error" : "bom-dialog-copy"}>{notice?.message}</p></ViewportDialog>
      {busy && <div className="fixed inset-0 z-[190] cursor-wait bg-black/[0.025]" aria-hidden="true" />}
    </div>
  );
}

function BomMaterialDialog({ row, onClose, onCreated }: { row: BomRow; onClose: () => void; onCreated: (material: InventoryMaterial, message: string) => void }) {
  const [form, setForm] = useState<MaterialPayload>({
    code: "", name: row.name || "", category: row.category || "其他", specification: row.specification || "",
    unit: row.unit || "件", material_type: row.acquisition_method === "内部加工" ? "自制件" : "原材料",
    default_supplier: "", minimum_stock: 0, brand: "", purchase_unit: row.unit || "件",
    purchase_conversion: 1, standard_sale_price: 0, reference_purchase_price: 0, safety_stock: 0,
    can_sell: false, can_purchase: row.acquisition_method !== "内部加工", manage_stock: true,
    can_subcontract: row.acquisition_method === "外协加工", remark: "由 BOM 临时项建立", is_active: true,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = <K extends keyof MaterialPayload>(key: K, value: MaterialPayload[K]) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async () => {
    if (!form.code.trim() || !form.name.trim() || !form.unit.trim()) { setError("物料编码、名称和单位为必填项"); return; }
    setBusy(true); setError("");
    try { const result = await createInventoryMaterial(form); onCreated(result.material, result.message); }
    catch (requestError) { setError(apiErrorMessage(requestError, "物料档案创建失败")); }
    finally { setBusy(false); }
  };
  return <ViewportDialog open title="临时项转为物料档案" description="建立一次通用物料资料，当前 BOM 行会自动关联；尺寸仍留在 BOM 规格中。" size="small" onClose={onClose} footer={<><button type="button" className="ui-button ui-button--secondary" disabled={busy} onClick={onClose}>取消</button><button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={() => void submit()}><Database size={15} />{busy ? "正在建档" : "创建并关联"}</button></>}><div className="bom-material-form"><label><span>物料编码 *</span><input autoFocus value={form.code} onChange={(event) => set("code", event.target.value)} placeholder="例如 PJ-CX-001" /></label><label><span>物料名称 *</span><input value={form.name} onChange={(event) => set("name", event.target.value)} /></label><label><span>分类</span><input value={form.category} onChange={(event) => set("category", event.target.value)} /></label><label><span>规格</span><input value={form.specification} onChange={(event) => set("specification", event.target.value)} /></label><label><span>单位 *</span><input value={form.unit} onChange={(event) => set("unit", event.target.value)} /></label><label><span>物料类型</span><select value={form.material_type} onChange={(event) => set("material_type", event.target.value)}>{["原材料", "配件", "半成品", "耗材", "采购件", "自制件", "外协件"].map((value) => <option key={value}>{value}</option>)}</select></label>{error && <p role="alert">{error}</p>}</div></ViewportDialog>;
}
