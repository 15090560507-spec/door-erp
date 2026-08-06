"use client";

const ERP_NEXT_URL = process.env.NEXT_PUBLIC_ERPNEXT_URL || "https://124.223.87.161:8443";

export default function ERPNextEntryButton() {
  return (
    <div className="rounded-lg border border-[#D7E8FF] bg-[#F5FAFF] p-3">
      <p className="text-xs text-[#4A6380]">生产订单、BOM、采购、仓储、质检和发货统一在 ERPNext 管理。</p>
      <button
        onClick={() => window.location.assign(ERP_NEXT_URL)}
        className="mt-2 w-full rounded-md bg-[#248A3D] py-2 text-sm font-semibold text-white hover:opacity-90"
      >
        进入 ERPNext 生产管理
      </button>
    </div>
  );
}
