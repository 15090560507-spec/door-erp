"use client";

export default function QuotePage() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 左侧：编辑区 */}
      <div className="space-y-4">
        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E] mb-4">报价明细</h2>
          <p className="text-[13px] text-[#8E8E93]">报价表单开发中...</p>
        </div>

        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E] mb-4">图纸识别</h2>
          <p className="text-[13px] text-[#8E8E93]">AI 识别面板开发中...</p>
        </div>
      </div>

      {/* 右侧：预览区 */}
      <div className="space-y-4">
        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6 min-h-[600px]">
          <h2 className="text-[15px] font-semibold text-[#1C1C1E] mb-4">报价单预览</h2>
          <p className="text-[13px] text-[#8E8E93]">预览区域开发中...</p>
        </div>

        <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-4">
          <div className="flex gap-2">
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#8E8E93]"
            >
              保存
            </button>
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#007AFF] text-white opacity-50"
            >
              导出 Excel
            </button>
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#8E8E93]"
            >
              导出 JPG
            </button>
            <button
              disabled
              className="flex-1 px-4 py-2 text-[13px] font-medium rounded-lg bg-[#F2F2F7] text-[#8E8E93]"
            >
              打印
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
