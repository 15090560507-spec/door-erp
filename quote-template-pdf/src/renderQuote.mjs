import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function numberText(value, digits = undefined) {
  if (value === null || value === undefined || value === "") return "";
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  return digits === undefined ? String(value) : n.toFixed(digits);
}

function isAreaUnit(unit) {
  const normalized = String(unit || "").toLowerCase();
  return normalized.includes("m2") || normalized.includes("㎡") || normalized.includes("m²");
}

function quoteQuantity(item) {
  if (!(item.productName || "").trim()) return "";
  if (item.quantity !== null && item.quantity !== undefined && item.quantity !== "") {
    const explicit = Number(item.quantity);
    if (Number.isFinite(explicit) && explicit > 0) {
      return isAreaUnit(item.unit) ? explicit.toFixed(4) : String(explicit);
    }
  }
  if (!isAreaUnit(item.unit)) return "1";
  const width = Number(item.width || 0);
  const height = Number(item.height || 0);
  if (!width || !height) return "";
  return (width * height * 0.000001).toFixed(4);
}

function quoteAmount(item) {
  const hasAnyItemValue = Boolean(
    (item.productName || "").trim()
    || item.width
    || item.height
    || (item.openDirection || "").trim()
    || (item.unit || "").trim()
    || item.unitPrice
  );
  if (!hasAnyItemValue) return "";

  const qty = Number(quoteQuantity(item));
  const unitPrice = Number(item.unitPrice || 0);
  if (!qty && !unitPrice) return unitPrice === 0 ? "0" : "";
  if (!qty || !Number.isFinite(unitPrice)) return "";
  return String(Math.round(qty * unitPrice));
}

function totalAmount(items) {
  return items.reduce((sum, item) => {
    const amount = Number(quoteAmount(item));
    return Number.isFinite(amount) ? sum + amount : sum;
  }, 0);
}

function toChineseAmount(value) {
  const n = Math.round(Number(value || 0));
  if (!n) return "";
  const digits = ["\u96f6", "\u58f9", "\u8d30", "\u53c1", "\u8086", "\u4f0d", "\u9646", "\u67d2", "\u634c", "\u7396"];
  const units = ["", "\u62fe", "\u4f70", "\u4edf"];
  const sections = ["", "\u4e07", "\u4ebf", "\u4e07\u4ebf"];

  function sectionToChinese(section) {
    let str = "";
    let zero = false;
    for (let i = 0; i < 4; i += 1) {
      const divisor = 10 ** (3 - i);
      const digit = Math.floor(section / divisor) % 10;
      const unitIndex = 3 - i;
      if (digit === 0) {
        zero = str.length > 0;
      } else {
        if (zero) str += digits[0];
        str += digits[digit] + units[unitIndex];
        zero = false;
      }
    }
    return str;
  }

  let remaining = n;
  let sectionIndex = 0;
  let result = "";
  let needZero = false;
  while (remaining > 0) {
    const section = remaining % 10000;
    if (section === 0) {
      needZero = result.length > 0;
    } else {
      let sectionText = sectionToChinese(section) + sections[sectionIndex];
      if (needZero || (section < 1000 && remaining >= 10000)) {
        sectionText = digits[0] + sectionText;
      }
      result = sectionText + result;
      needZero = false;
    }
    remaining = Math.floor(remaining / 10000);
    sectionIndex += 1;
  }
  return `\u4eba\u6c11\u5e01${result}\u5143\u6574`;
}

function quoteGroups(quote) {
  if (Array.isArray(quote.doorGroups) && quote.doorGroups.length) {
    return quote.doorGroups.map((group, index) => ({
      groupName: group.groupName || `第${index + 1}樘门`,
      items: Array.isArray(group.items) ? group.items : [],
    }));
  }
  return [{
    groupName: "第1樘门",
    items: Array.isArray(quote.items) ? quote.items : [],
  }];
}

function renderItemRows(groups, minimumItemRows) {
  const rows = [];
  let sequence = 0;
  let itemCount = 0;
  groups.forEach((group, groupIndex) => {
    group.items.forEach((item, itemIndex) => {
      const hasProduct = Boolean((item.productName || "").trim());
      if (hasProduct) sequence += 1;
      itemCount += 1;
      rows.push(`<tr class="item-row">
        <td class="item cell-center">${hasProduct ? sequence : ""}</td>
        <td class="item product" colspan="2">${escapeHtml(item.productName || "")}</td>
        <td class="item cell-center">${escapeHtml(numberText(item.width))}</td>
        <td class="item cell-center">${escapeHtml(numberText(item.height))}</td>
        <td class="item cell-center">${escapeHtml(itemIndex === 0 ? item.openDirection || "" : "")}</td>
        <td class="item cell-center">${escapeHtml(item.unit || "")}</td>
        <td class="item cell-center">${escapeHtml(quoteQuantity(item))}</td>
        <td class="item cell-center">${escapeHtml(numberText(item.unitPrice))}</td>
        <td class="item cell-center">${escapeHtml(quoteAmount(item))}</td>
      </tr>`);
    });
    if (groups.length > 1) {
      rows.push(`<tr class="group-subtotal">
        <td colspan="9">${escapeHtml(group.groupName)}小计</td>
        <td class="cell-center">${escapeHtml(totalAmount(group.items))}</td>
      </tr>`);
    }
  });
  for (let index = itemCount; index < minimumItemRows; index += 1) {
    rows.push(`<tr class="item-row">
      <td></td><td colspan="2"></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>
    </tr>`);
  }

  return rows.join("\n");
}

function buildLayoutCss(layout) {
  const columnRules = layout.columns
    .map((column) => `.quote-sheet col.${column.className} { width: ${column.millimeters}mm; }`)
    .join("\n");
  const heights = layout.rowHeightsMm;
  return `${columnRules}
.quote-sheet tr.r1 { height: ${heights.title}mm; }
.quote-sheet tr.r3, .quote-sheet tr.r4 { height: ${heights.header}mm; }
.quote-sheet tr.r5, .quote-sheet tr.r6 { height: ${heights.introPart}mm; }
.quote-sheet tr.r7, .quote-sheet tr.r8 { height: ${heights.tableHeader}mm; }
.quote-sheet tr.item-row { height: ${heights.item}mm; }
.quote-sheet tr.group-subtotal { height: ${heights.subtotal}mm; }
.quote-sheet tr.r17 { height: ${heights.total}mm; }
.quote-sheet tr.r18 { height: ${heights.amount}mm; }
.quote-sheet tr.r19 { height: ${heights.notice}mm; }
.quote-sheet tr.r20, .quote-sheet tr.r21, .quote-sheet tr.r22 { height: ${heights.termsPart}mm; }
.quote-sheet tr.r23 { height: ${heights.invoice}mm; }
.quote-sheet tr.r24 { height: ${heights.bank}mm; }
.head { color: #${layout.colors.headerText}; }
.group-subtotal td { background: #${layout.colors.subtotalFill}; }
.total-row td { background: #${layout.colors.totalFill}; }
.notice { color: #${layout.colors.noticeText}; }
.yellow { background: #${layout.colors.infoFill}; color: #${layout.colors.noticeText}; }`;
}

function renderHtml(quote, cssText, layout) {
  const groups = quoteGroups(quote);
  const items = groups.flatMap((group) => group.items);
  const total = totalAmount(items);
  const noticeText = quote.noticeText || layout.defaultNoticeText;

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>报价单</title>
  <style>${cssText}\n${buildLayoutCss(layout)}</style>
</head>
<body>
  <main class="page">
    <table class="quote-sheet" aria-label="产品报价单">
      <colgroup>
        <col class="col-a"><col class="col-b"><col class="col-c"><col class="col-d"><col class="col-e">
        <col class="col-f"><col class="col-g"><col class="col-h"><col class="col-i"><col class="col-j">
      </colgroup>
      <tbody>
        <tr class="r1"><td class="title" colspan="10">${escapeHtml(layout.companyName)}</td></tr>
        <tr class="r3">
          <td class="label" colspan="2">客户名称:</td>
          <td class="value" colspan="4">${escapeHtml(quote.customerName || "")}</td>
          <td class="label" colspan="2">日期:</td>
          <td class="value date-value" colspan="2">${escapeHtml(quote.quoteDate || "")}</td>
        </tr>
        <tr class="r4">
          <td class="label" colspan="2">项目名称:</td>
          <td class="value" colspan="4">${escapeHtml(quote.projectName || "")}</td>
          <td class="label" colspan="2">主题:</td>
          <td class="value subject-value" colspan="2">产品报价单</td>
        </tr>
        <tr class="r5">
          <td class="intro" colspan="10" rowspan="2">${escapeHtml(layout.introText)}</td>
        </tr>
        <tr class="r6"></tr>
        <tr class="r7">
          <td class="head" rowspan="2">序号</td>
          <td class="head" colspan="2" rowspan="2">品名型号</td>
          <td class="head spec" colspan="2">规格</td>
          <td class="head" rowspan="2">开启方向</td>
          <td class="head" rowspan="2">单位</td>
          <td class="head" rowspan="2">数量</td>
          <td class="head" rowspan="2">单价</td>
          <td class="head" rowspan="2">总金额/元</td>
        </tr>
        <tr class="r8">
          <td class="head">宽</td>
          <td class="head">高</td>
        </tr>
        ${renderItemRows(groups, layout.minimumItemRows)}
        <tr class="r17 total-row">
          <td class="total-label">合计</td>
          <td colspan="2"></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td class="cell-center">${escapeHtml(total)}</td>
        </tr>
        <tr class="r18">
          <td class="amount-label" colspan="5">合计总金额（大写）:</td>
          <td class="amount-text" colspan="5">${escapeHtml(toChineseAmount(total))}</td>
        </tr>
        <tr class="r19">
          <td class="notice" colspan="10">${escapeHtml(noticeText)}</td>
        </tr>
        <tr class="r20">
          <td class="yellow terms" colspan="10" rowspan="3">${escapeHtml(layout.termsText)}</td>
        </tr>
        <tr class="r21"></tr>
        <tr class="r22"></tr>
        <tr class="r23">
          <td class="yellow invoice" colspan="10">${escapeHtml(layout.invoiceText)}</td>
        </tr>
        <tr class="r24">
          <td class="yellow bank" colspan="10">${escapeHtml(layout.bankText)}</td>
        </tr>
      </tbody>
    </table>
  </main>
</body>
</html>`;
}

export async function buildQuoteHtml(quotePath) {
  const [quoteText, cssText, layoutText] = await Promise.all([
    fs.readFile(quotePath, "utf8"),
    fs.readFile(path.join(__dirname, "template.css"), "utf8"),
    fs.readFile(path.join(__dirname, "..", "layout.json"), "utf8"),
  ]);
  return renderHtml(JSON.parse(quoteText), cssText, JSON.parse(layoutText));
}
