"use client";

import type { QuoteItem } from "@/lib/quoteTypes";
import { toChineseAmount } from "@/lib/toChineseAmount";

interface Props {
  customerName: string;
  projectName: string;
  quoteDate: string;
  noticeText: string;
  items: QuoteItem[];
}

function numberText(value: number | null | undefined, digits?: number) {
  if (value === null || value === undefined || value === 0) return value === 0 ? "0" : "";
  return digits === undefined ? String(value) : Number(value).toFixed(digits);
}

function isAreaUnit(unit: string) {
  const normalized = (unit || "").toLowerCase();
  return normalized.includes("m2") || normalized.includes("㎡") || normalized.includes("m²");
}

function quoteQuantity(item: QuoteItem) {
  if (!item.productName.trim()) return "";
  if (!isAreaUnit(item.unit)) return "1";
  const width = Number(item.width || 0);
  const height = Number(item.height || 0);
  if (!width || !height) return "";
  return (width * height * 0.000001).toFixed(4);
}

function quoteAmount(item: QuoteItem) {
  const qty = Number(quoteQuantity(item));
  const unitPrice = Number(item.unitPrice || 0);
  const hasAnyValue = Boolean(
    item.productName.trim() ||
    item.width ||
    item.height ||
    item.openDirection.trim() ||
    item.unit.trim() ||
    item.unitPrice
  );

  if (!hasAnyValue) return "";
  if (!qty && !unitPrice) return "0";
  if (!qty || !Number.isFinite(unitPrice)) return "";
  return String(Math.round(qty * unitPrice));
}

export default function QuotePreview({ customerName, projectName, quoteDate, noticeText, items }: Props) {
  const rows = Array.from({ length: 8 }, (_, index) => items[index]);
  const total = rows.reduce((sum, item) => {
    if (!item) return sum;
    const amount = Number(quoteAmount(item));
    return Number.isFinite(amount) ? sum + amount : sum;
  }, 0);

  const cell = "border border-black px-[4px] align-middle overflow-hidden";
  const head = `${cell} text-center font-bold text-[#00005e] whitespace-nowrap`;
  const itemCell = `${cell} text-center font-bold leading-tight`;
  const yellow = `${cell} bg-[#ffff00] text-[#ff0000] font-bold leading-snug`;

  return (
    <div id="quote-preview-area" className="bg-white rounded-2xl border border-[#E5E5EA]/60 p-3 overflow-auto">
      <div className="mx-auto w-full max-w-[760px] bg-white">
        <table
          className="w-full table-fixed border-collapse border border-black text-black"
          style={{
            fontFamily:
              '"SimSun", "Songti SC", "AR PL UMing CN", "Noto Serif CJK SC", "Source Han Serif SC", "Microsoft YaHei", serif',
          }}
        >
          <colgroup>
            <col style={{ width: "7.25%" }} />
            <col style={{ width: "8.9%" }} />
            <col style={{ width: "25.82%" }} />
            <col style={{ width: "8.85%" }} />
            <col style={{ width: "8.9%" }} />
            <col style={{ width: "8.51%" }} />
            <col style={{ width: "5.03%" }} />
            <col style={{ width: "6.96%" }} />
            <col style={{ width: "6.09%" }} />
            <col style={{ width: "13.69%" }} />
          </colgroup>
          <tbody>
            <tr className="h-[42px]">
              <td className={`${cell} text-center text-[20px] font-bold leading-none`} colSpan={10}>
                浙江西州将军门业有限公司
              </td>
            </tr>

            <tr className="h-[30px]">
              <td className={`${cell} text-[15px] font-bold`} colSpan={2}>客户名称:</td>
              <td className={`${cell} text-[15px] font-bold`} colSpan={4}>{customerName}</td>
              <td className={`${cell} text-[15px] font-bold`} colSpan={2}>日期:</td>
              <td className={`${cell} text-center text-[15px] font-bold tracking-[2px]`} colSpan={2}>{quoteDate}</td>
            </tr>
            <tr className="h-[30px]">
              <td className={`${cell} text-[15px] font-bold`} colSpan={2}>项目名称:</td>
              <td className={`${cell} text-[15px] font-bold`} colSpan={4}>{projectName}</td>
              <td className={`${cell} text-[15px] font-bold`} colSpan={2}>主题:</td>
              <td className={`${cell} text-center text-[15px] font-bold tracking-[2px]`} colSpan={2}>产品报价单</td>
            </tr>

            <tr className="h-[86px]">
              <td className={`${cell} text-[15px] font-bold leading-relaxed indent-8`} colSpan={10}>
                承蒙关照，感谢贵方对我方产品感兴趣，根据贵方要求，报上我公司价格，可随时来电来函告知，我们将及时为您提供。
              </td>
            </tr>

            <tr className="h-[28px]">
              <td className={head} rowSpan={2}>序号</td>
              <td className={head} colSpan={2} rowSpan={2}>品名型号</td>
              <td className={head} colSpan={2}>规格</td>
              <td className={head} rowSpan={2}>开启方向</td>
              <td className={head} rowSpan={2}>单位</td>
              <td className={head} rowSpan={2}>数量</td>
              <td className={head} rowSpan={2}>单价</td>
              <td className={head} rowSpan={2}>总金额/元</td>
            </tr>
            <tr className="h-[28px]">
              <td className={head}>宽</td>
              <td className={head}>高</td>
            </tr>

            {rows.map((item, index) => {
              const hasProduct = Boolean(item?.productName.trim());
              return (
                <tr className="h-[34px]" key={index}>
                  <td className={itemCell}>{hasProduct ? index + 1 : ""}</td>
                  <td className={`${itemCell} text-left`} colSpan={2}>{item?.productName || ""}</td>
                  <td className={itemCell}>{numberText(item?.width)}</td>
                  <td className={itemCell}>{numberText(item?.height)}</td>
                  <td className={itemCell}>{index === 0 ? item?.openDirection || "" : ""}</td>
                  <td className={itemCell}>{item?.unit || ""}</td>
                  <td className={itemCell}>{item ? quoteQuantity(item) : ""}</td>
                  <td className={itemCell}>{numberText(item?.unitPrice)}</td>
                  <td className={itemCell}>{item ? quoteAmount(item) : ""}</td>
                </tr>
              );
            })}

            <tr className="h-[28px] bg-[#00b0f0] text-[16px] font-bold">
              <td className={cell}>合计</td>
              <td className={cell} colSpan={2}></td>
              <td className={cell}></td>
              <td className={cell}></td>
              <td className={cell}></td>
              <td className={cell}></td>
              <td className={cell}></td>
              <td className={cell}></td>
              <td className={`${cell} text-center`}>{total}</td>
            </tr>

            <tr className="h-[32px]">
              <td className={`${cell} text-[16px] font-bold`} colSpan={5}>合计总金额（大写）:</td>
              <td className={`${cell} text-right text-[14px] font-bold`} colSpan={5}>{total ? toChineseAmount(total) : ""}</td>
            </tr>
            <tr className="h-[46px]">
              <td className={`${cell} text-center text-[#ff0000] text-[15px] font-bold`} colSpan={10}>
                {noticeText}
              </td>
            </tr>
            <tr className="h-[86px]">
              <td className={`${yellow} text-[14px] whitespace-pre-wrap`} colSpan={10}>
                {`1.付款方式:确定制作，先安排货款50%的定金，款清发货
2.以上价格不包含运费、安装调试费、测量等费用。
3.请及时确定签字回传，我司以收到贵方签字回传单以及保证金为准，方可安排生产`}
              </td>
            </tr>
            <tr className="h-[110px]">
              <td className={`${yellow} text-[14px] whitespace-pre-wrap`} colSpan={10}>
                {`开票资料:对公账户公司名称杭州浙家门业有限公司账产
号码:3301041060000451769                                                开户银行:杭州银行富阳支行
法定代表人:王家龙基本存款
账户编号:J3310198780901`}
              </td>
            </tr>
            <tr className="h-[86px]">
              <td className={`${yellow} text-[14px] whitespace-pre-wrap`} colSpan={10}>
                {`汇款请汇入以下账户
户名：张春兰
账号：622848 0329 2739 08775
汇款行农业银行浙江省分行杭州市上泗支行`}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
