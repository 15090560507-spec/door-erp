"use client";

import { useEffect, useState } from "react";
import { disableProductionMaterial, getProductionMaterials, saveProductionMaterial } from "@/lib/productionApi";
import type { ProductionMaterial } from "@/lib/productionTypes";

const emptyForm = {
  code: "",
  name: "",
  category: "其他",
  material: "",
  specification: "",
  thickness: "",
  unit: "",
  supplier: "",
  warehouse_location: "",
  remark: "",
  active: true,
};

export default function ProductionMaterials({ canEdit, notify }: { canEdit: boolean; notify: (message: string, error?: boolean) => void }) {
  const [materials, setMaterials] = useState<ProductionMaterial[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | undefined>();

  const load = async () => {
    try { setMaterials(await getProductionMaterials()); }
    catch (error) { notify(apiMessage(error, "生产物料加载失败"), true); }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    if (!form.code.trim() || !form.name.trim()) return notify("请填写物料编码和名称", true);
    try {
      await saveProductionMaterial(form, editingId);
      setForm(emptyForm);
      setEditingId(undefined);
      await load();
      notify("生产物料已保存");
    } catch (error) { notify(apiMessage(error, "保存物料失败"), true); }
  };

  return (
    <section className="space-y-4">
      {canEdit && (
        <div className="border border-[#E5E5EA] bg-white p-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="物料编码" value={form.code} onChange={(value) => setForm({ ...form, code: value })} />
            <Field label="物料名称" value={form.name} onChange={(value) => setForm({ ...form, name: value })} />
            <SelectField label="分类" value={form.category} onChange={(value) => setForm({ ...form, category: value })} options={['板材', '型材', '玻璃', '锁具', '拉手', '合页', '包装', '其他']} />
            <Field label="规格" value={form.specification} onChange={(value) => setForm({ ...form, specification: value })} />
            <Field label="单位" value={form.unit} onChange={(value) => setForm({ ...form, unit: value })} />
            <Field label="材质" value={form.material} onChange={(value) => setForm({ ...form, material: value })} />
            <Field label="厚度" value={form.thickness} onChange={(value) => setForm({ ...form, thickness: value })} />
            <Field label="供应商" value={form.supplier} onChange={(value) => setForm({ ...form, supplier: value })} />
            <Field label="仓位" value={form.warehouse_location} onChange={(value) => setForm({ ...form, warehouse_location: value })} />
            <div className="flex items-end gap-2">
              <button onClick={save} className="h-10 flex-1 bg-[#007AFF] px-4 text-sm font-medium text-white">{editingId ? '更新' : '新增物料'}</button>
              {editingId && <button onClick={() => { setEditingId(undefined); setForm(emptyForm); }} className="h-10 border border-[#C7C7CC] px-3 text-sm">取消</button>}
            </div>
          </div>
        </div>
      )}
      <div className="overflow-x-auto border border-[#E5E5EA] bg-white">
        <table className="min-w-[900px] w-full text-sm">
          <thead className="bg-[#F7F7F9] text-left text-xs text-[#636366]"><tr>{['编码', '名称', '分类', '材质', '规格', '厚度', '单位', '供应商', '仓位', '操作'].map((label) => <th key={label} className="border-b border-[#E5E5EA] px-3 py-3 font-medium">{label}</th>)}</tr></thead>
          <tbody>{materials.map((item) => (
            <tr key={item.id} className="border-b border-[#F2F2F7]">
              <td className="px-3 py-3 font-medium">{item.code}</td><td className="px-3 py-3">{item.name}</td><td className="px-3 py-3">{item.category}</td>
              <td className="px-3 py-3">{item.material}</td><td className="px-3 py-3">{item.specification}</td><td className="px-3 py-3">{item.thickness}</td>
              <td className="px-3 py-3">{item.unit}</td><td className="px-3 py-3">{item.supplier}</td><td className="px-3 py-3">{item.warehouse_location}</td>
              <td className="whitespace-nowrap px-3 py-3">{canEdit && <><button onClick={() => { setEditingId(item.id); setForm({ ...emptyForm, ...item, active: Boolean(item.active) }); }} className="mr-3 text-[#007AFF]">编辑</button><button onClick={async () => { await disableProductionMaterial(item.id); await load(); notify('物料已停用'); }} className="text-[#FF3B30]">停用</button></>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-xs text-[#636366]"><span className="mb-1 block">{label}</span><input value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm outline-none focus:border-[#007AFF]" /></label>;
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
  return <label className="block text-xs text-[#636366]"><span className="mb-1 block">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 w-full border border-[#C7C7CC] bg-white px-3 text-sm">{options.map((option) => <option key={option}>{option}</option>)}</select></label>;
}

function apiMessage(error: unknown, fallback: string) {
  return (error as { userMessage?: string })?.userMessage || fallback;
}
