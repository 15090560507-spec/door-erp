"use client";

import { Pencil, Plus, Search, Workflow } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import ViewportDialog from "@/components/workspace/ViewportDialog";
import { DOOR_TYPES, PRODUCT_NAMES } from "@/lib/types";
import {
  createInventoryBomRule,
  getInventoryBomRules,
  getInventoryMaterials,
  updateInventoryBomRule,
} from "@/lib/inventoryApi";
import type { BomRulePayload, InventoryBomRule, InventoryMaterial } from "@/lib/inventoryTypes";

const GROUPS = [
  ["frame", "门框与门槛"], ["panel", "门扇与面板"], ["skeleton", "骨架与型材"],
  ["trim", "门套/门头/门柱"], ["glass", "玻璃与线条"], ["hardware", "五金与开启机构"],
  ["ornament", "花件与外购装饰"], ["consumable", "辅料与耗材"], ["packaging", "包装"],
  ["subcontract", "外协加工"],
] as const;

const CONDITION_FIELDS = [
  ["", "无附加条件"], ["ys", "颜色"], ["material", "材质"], ["sel_hys", "开启机构"],
  ["st_val", "锁体类型"], ["fingerprint_lock", "指纹锁"], ["glass_spec", "玻璃规格"],
  ["sel_bz", "包装方式"], ["has_outer", "外包套"], ["has_inner", "内包套"],
] as const;

const EMPTY: BomRulePayload = {
  code: "", name: "", material_id: 0, group_code: "consumable", product_name: "", door_type: "",
  condition_field: "", condition_value: "", quantity_value: 1, quantity_basis: "每樘", waste_rate: 0,
  operation_code: "CUSTOM", acquisition_method: "库存/采购", priority: 100, remark: "", is_active: true,
};

export default function BomRuleCatalog({ notify }: { notify: (message: string, error?: boolean) => void }) {
  const [rules, setRules] = useState<InventoryBomRule[]>([]);
  const [materials, setMaterials] = useState<InventoryMaterial[]>([]);
  const [q, setQ] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<InventoryBomRule | "new" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [nextRules, nextMaterials] = await Promise.all([
        getInventoryBomRules({ q: q || undefined, include_inactive: includeInactive }),
        getInventoryMaterials(),
      ]);
      setRules(nextRules);
      setMaterials(nextMaterials);
    } catch (error) {
      notify(apiMessage(error, "BOM 规则加载失败"), true);
    } finally {
      setLoading(false);
    }
  }, [includeInactive, notify, q]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return <section className="border border-[#D1D1D6] bg-white">
    <header className="flex flex-wrap items-center gap-2 border-b border-[#E5E5EA] p-4">
      <div className="mr-auto min-w-[240px]"><h2 className="flex items-center gap-2 font-semibold"><Workflow size={17} />BOM 规则模板</h2><p className="mt-1 text-xs text-[#636366]">启用规则只影响此后生成或重新生成的草稿 BOM，已发布版本保持不变。</p></div>
      <div className="relative min-w-[220px] flex-1 sm:max-w-72"><Search size={15} className="pointer-events-none absolute left-3 top-2.5 text-[#8E8E93]"/><input value={q} onChange={(event) => setQ(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void load()} placeholder="规则、物料编码或名称" className="h-9 w-full border border-[#C7C7CC] pl-9 pr-3 text-sm" /></div>
      <label className="flex h-9 items-center gap-2 border border-[#C7C7CC] px-3 text-sm"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />含停用</label>
      <button type="button" onClick={() => void load()} className="ui-button ui-button--secondary">查询</button>
      <button type="button" onClick={() => setEditing("new")} className="ui-button ui-button--primary"><Plus size={15}/>新增规则</button>
    </header>
    <div className="divide-y divide-[#E5E5EA]">
      {loading ? <Empty text="正在加载..." /> : rules.length ? rules.map((rule) => <button key={rule.id} type="button" onClick={() => setEditing(rule)} className="grid w-full gap-3 px-4 py-4 text-left transition-colors hover:bg-[#F8F8FA] md:grid-cols-[minmax(180px,1.1fr)_minmax(220px,1.4fr)_minmax(180px,1fr)_130px_34px] md:items-center">
        <div className="min-w-0"><div className="flex items-center gap-2"><strong className="truncate text-sm">{rule.name}</strong><span className={`shrink-0 px-2 py-0.5 text-[11px] ${rule.is_active ? "bg-[#E7F7EA] text-[#248A3D]" : "bg-[#F2F2F7] text-[#8E8E93]"}`}>{rule.is_active ? "启用" : "停用"}</span></div><span className="mt-1 block text-xs text-[#636366]">{rule.code} · 优先级 {rule.priority}</span></div>
        <div className="min-w-0"><strong className="block truncate text-sm">{rule.material_code} · {rule.material_name}</strong><span className="mt-1 block truncate text-xs text-[#636366]">{rule.material_specification || "无规格"} · {groupLabel(rule.group_code)}</span></div>
        <div className="text-xs text-[#636366]"><span className="block">{scopeText(rule)}</span><span className="mt-1 block">{conditionText(rule)}</span></div>
        <div className="text-xs"><strong className="block text-sm">{rule.quantity_value} {rule.material_unit}/{rule.quantity_basis === "每扇" ? "扇" : "樘"}</strong><span className="mt-1 block text-[#636366]">损耗 {rule.waste_rate}%</span></div>
        <Pencil size={16} className="text-[#636366]" />
      </button>) : <Empty text="暂无 BOM 规则。先建立内部物料，再新增一条匹配规则。" />}
    </div>
    <RuleDialog key={editing === "new" ? "new" : editing?.id || "closed"} open={Boolean(editing)} rule={editing && editing !== "new" ? editing : null} materials={materials} onClose={() => setEditing(null)} onSaved={async (message) => { setEditing(null); notify(message); await load(); }} notify={notify} />
  </section>;
}

function RuleDialog({ open, rule, materials, onClose, onSaved, notify }: { open: boolean; rule: InventoryBomRule | null; materials: InventoryMaterial[]; onClose: () => void; onSaved: (message: string) => Promise<void>; notify: (message: string, error?: boolean) => void }) {
  const initial: BomRulePayload = rule ? {
    code: rule.code, name: rule.name, material_id: rule.material_id, group_code: rule.group_code,
    product_name: rule.product_name, door_type: rule.door_type, condition_field: rule.condition_field,
    condition_value: rule.condition_value, quantity_value: rule.quantity_value, quantity_basis: rule.quantity_basis,
    waste_rate: rule.waste_rate, operation_code: rule.operation_code, acquisition_method: rule.acquisition_method,
    priority: rule.priority, remark: rule.remark, is_active: Boolean(rule.is_active),
  } : EMPTY;
  const [form, setForm] = useState<BomRulePayload>(initial);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof BomRulePayload>(key: K, value: BomRulePayload[K]) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async () => {
    if (!form.code.trim() || !form.name.trim() || !form.material_id || !form.group_code) { notify("规则编码、名称、BOM 分组和内部物料为必填项", true); return; }
    if (form.condition_value.trim() && !form.condition_field) { notify("填写参数值前请先选择参数字段", true); return; }
    setBusy(true);
    try {
      const result = rule ? await updateInventoryBomRule(rule.id, form) : await createInventoryBomRule(form);
      await onSaved(result.message);
    } catch (error) { notify(apiMessage(error, "BOM 规则保存失败"), true); }
    finally { setBusy(false); }
  };
  return <ViewportDialog open={open} title={rule ? "编辑 BOM 规则" : "新增 BOM 规则"} description="条件留空表示全部适用；多个参数值可用 | 分隔，例如 左开|右开。" size="large" onClose={onClose} footer={<><button type="button" className="ui-button ui-button--secondary" onClick={onClose}>取消</button><button type="button" className="ui-button ui-button--primary" disabled={busy} onClick={() => void submit()}>{busy ? "正在保存..." : "保存规则"}</button></>}>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="规则编码 *"><input disabled={Boolean(rule)} value={form.code} onChange={(event) => set("code", event.target.value)} className="form-control disabled:bg-[#F2F2F7]" placeholder="例如 HW-HINGE-01" /></Field>
      <Field label="规则名称 *"><input value={form.name} onChange={(event) => set("name", event.target.value)} className="form-control" placeholder="例如 单门标准合页" /></Field>
      <Field label="内部物料 *"><select value={form.material_id || ""} onChange={(event) => set("material_id", Number(event.target.value) || 0)} className="form-control"><option value="">请选择物料</option>{materials.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name} {item.specification}</option>)}</select></Field>
      <Field label="BOM 分组 *"><select value={form.group_code} onChange={(event) => set("group_code", event.target.value)} className="form-control">{GROUPS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field label="适用产品"><select value={form.product_name} onChange={(event) => set("product_name", event.target.value)} className="form-control"><option value="">全部产品</option>{PRODUCT_NAMES.map((item) => <option key={item}>{item}</option>)}</select></Field>
      <Field label="适用门型"><select value={form.door_type} onChange={(event) => set("door_type", event.target.value)} className="form-control"><option value="">全部门型</option>{DOOR_TYPES.map((item) => <option key={item}>{item}</option>)}</select></Field>
      <Field label="附加参数"><select value={form.condition_field} onChange={(event) => set("condition_field", event.target.value)} className="form-control">{CONDITION_FIELDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field label="参数值"><input value={form.condition_value} onChange={(event) => set("condition_value", event.target.value)} disabled={!form.condition_field} className="form-control disabled:bg-[#F2F2F7]" placeholder={form.condition_field ? "精确值，多个值用 | 分隔" : "无需填写"} /></Field>
      <Field label="工序代码"><input value={form.operation_code} onChange={(event) => set("operation_code", event.target.value)} className="form-control" /></Field>
      <Field label="基础数量 *"><input type="number" min="0.0001" step="0.01" value={form.quantity_value} onChange={(event) => set("quantity_value", Number(event.target.value) || 0)} className="form-control" /></Field>
      <Field label="数量口径"><select value={form.quantity_basis} onChange={(event) => set("quantity_basis", event.target.value as "每樘" | "每扇")} className="form-control"><option>每樘</option><option>每扇</option></select></Field>
      <Field label="损耗率 (%)"><input type="number" min="0" max="100" step="0.1" value={form.waste_rate} onChange={(event) => set("waste_rate", Number(event.target.value) || 0)} className="form-control" /></Field>
      <Field label="供应方式"><select value={form.acquisition_method} onChange={(event) => set("acquisition_method", event.target.value)} className="form-control">{["库存/采购", "采购", "库存", "内部加工", "外协"].map((item) => <option key={item}>{item}</option>)}</select></Field>
      <Field label="优先级"><input type="number" min="0" max="9999" value={form.priority} onChange={(event) => set("priority", Number(event.target.value) || 0)} className="form-control" /></Field>
      {rule && <Field label="状态"><label className="flex h-10 items-center gap-2 border border-[#C7C7CC] px-3 text-sm"><input type="checkbox" checked={Boolean(form.is_active)} onChange={(event) => set("is_active", event.target.checked)} />启用此规则</label></Field>}
      <label className="text-xs text-[#636366] sm:col-span-2 lg:col-span-3">备注<textarea value={form.remark} onChange={(event) => set("remark", event.target.value)} className="mt-1 min-h-20 w-full border border-[#C7C7CC] p-3 text-sm text-[#1C1C1E]" /></label>
    </div>
  </ViewportDialog>;
}

function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="text-xs text-[#636366]">{label}<span className="mt-1 block">{children}</span></label>; }
function Empty({ text }: { text: string }) { return <div className="px-4 py-20 text-center text-sm text-[#8E8E93]">{text}</div>; }
function groupLabel(code: string) { return GROUPS.find(([value]) => value === code)?.[1] || code; }
function scopeText(rule: InventoryBomRule) { return [rule.product_name || "全部产品", rule.door_type || "全部门型"].join(" · "); }
function conditionText(rule: InventoryBomRule) { const label = CONDITION_FIELDS.find(([value]) => value === rule.condition_field)?.[1]; return label ? `${label} = ${rule.condition_value || "有值"}` : "无附加条件"; }
function apiMessage(error: unknown, fallback: string) { return (error as { userMessage?: string; message?: string })?.userMessage || (error as { message?: string })?.message || fallback; }
