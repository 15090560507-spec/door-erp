"use client";

import type { QuoteItem } from "@/lib/quoteTypes";
import { toChineseAmount } from "@/lib/toChineseAmount";

interface Props {
  customerName: string;
  projectName: string;
  quoteDate: string;
  items: QuoteItem[];
}

export default function QuotePreview({ customerName, projectName, quoteDate, items }: Props) {
  const displayItems = items.filter((item) => item.productName.trim());

  let total = 0;
  const rows = Array.from({ length: 8 }, (_, i) => {
    const item = displayItems[i];
    if (!item) return null;
    const width = item.width || 0;
    const height = item.height || 0;
    const unitPrice = item.unitPrice || 0;
    const quantity = width && height ? width * height * 0.000001 : 0;
    const amount = quantity && unitPrice ? Math.round(quantity * unitPrice) : 0;
    total += amount;
    return { ...item, index: i + 1, quantity, amount };
  });

  const displayDate = quoteDate || new Date().toISOString().slice(0, 10);

  return (
    <div className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-6 min-h-[600px]">
      {/* Company Header */}
      <h2 className="text-[18px] font-bold text-[#1C1C1E] text-center mb-4">
        浙江西州将军门业有限公司
      </h2>

      {/* Meta Info */}
      <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 mb-4 text-[13px]">
        <div>
          <span className="text-[#8E8E93]">客户名称：</span>
          <span className="text-[#1C1C1E] font-medium">{customerName || " "}</span>
        </div>
        <div>
          <span className="text-[#8E8E93]">日期：</span>
          <span className="text-[#1C1C1E] font-medium">{displayDate}</span>
        </div>
        <div>
          <span className="text-[#8E8E93]">项目名称：</span>
          <span className="text-[#1C1C1E] font-medium">{projectName || " "}</span>
        </div>
        <div>
          <span className="text-[#8E8E93]">主题：</span>
          <span className="text-[#1C1C1E] font-medium">产品报价单</span>
        </div>
      </div>

      <p className="text-[11px] text-[#8E8E93] mb-4">
        此预览仅用于录入时快速确认，正式导出以模板为准。
      </p>

      {/* Items Table */}
      <table className="w-full text-[12px] border-collapse mb-3">
        <thead>
          <tr className="border-b-2 border-[#1C1C1E]">
            <th rowSpan={2} className="py-1.5 px-1 text-center w-[40px]">序号</th>
            <th rowSpan={2} className="py-1.5 px-1 text-left">品名型号</th>
            <th colSpan={2} className="py-1.5 px-1 text-center">规格</th>
            <th rowSpan={2} className="py-1.5 px-1 text-center w-[60px]">开启方向</th>
            <th rowSpan={2} className="py-1.5 px-1 text-center w-[45px]">单位</th>
            <th rowSpan={2} className="py-1.5 px-1 text-center w-[50px]">数量</th>
            <th rowSpan={2} className="py-1.5 px-1 text-center w-[60px]">单价</th>
            <th rowSpan={2} className="py-1.5 px-1 text-center w-[70px]">总金额/元</th>
          </tr>
          <tr className="border-b-2 border-[#1C1C1E]">
            <th className="py-1 px-1 text-center w-[45px]">宽</th>
            <th className="py-1 px-1 text-center w-[45px]">高</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-[#E5E5EA]/40">
              <td className="py-1 px-1 text-center text-[#8E8E93]">{row?.index || ""}</td>
              <td className="py-1 px-1">{row?.productName || ""}</td>
              <td className="py-1 px-1 text-center">{row?.width || ""}</td>
              <td className="py-1 px-1 text-center">{row?.height || ""}</td>
              <td className="py-1 px-1 text-center">{row?.openDirection || ""}</td>
              <td className="py-1 px-1 text-center">{row?.unit || ""}</td>
              <td className="py-1 px-1 text-center">{row ? row.quantity.toFixed(4) : ""}</td>
              <td className="py-1 px-1 text-center">{row?.unitPrice || ""}</td>
              <td className="py-1 px-1 text-center">{row?.amount || ""}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={8} className="py-1.5 px-1 text-right font-medium text-[13px]">合计</td>
            <td className="py-1.5 px-1 text-center font-bold text-[13px]">{total || "0"}</td>
          </tr>
        </tfoot>
      </table>

      {/* Chinese Amount */}
      <div className="text-[13px] mb-3">
        <span className="text-[#8E8E93]">合计总金额（大写）：</span>
        <span className="text-[#1C1C1E] font-medium">{toChineseAmount(total) || " "}</span>
      </div>

      {/* Footer */}
      <p className="text-[11px] text-[#8E8E93] mb-2">本报价不含税工厂结算价，不含木箱。</p>
      <div className="text-[11px] text-[#8E8E93] space-y-0.5">
        <p>1. 付款方式：确定制作，先安排货款 50% 的定金，款清发货。</p>
        <p>2. 费用说明：以上价格不包含运输、安装、测量等费用。</p>
        <p>3. 确认流程：请及时确认签字回传，以便安排生产。</p>
      </div>
    </div>
  );
}
