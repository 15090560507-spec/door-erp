/**
 * Convert a number to Chinese uppercase amount format.
 * Example: 12345 -> "人民币壹万贰仟叁佰肆拾伍元整"
 */
export function toChineseAmount(num: number): string {
  const n = Math.round(num);
  if (!n || n <= 0) return "";

  const digits = ["零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖"];
  const units = ["", "拾", "佰", "仟"];
  const sections = ["", "万", "亿", "兆"];

  function sectionToChinese(section: number): string {
    let output = "";
    let zeroPending = false;
    let s = section;
    for (let i = 0; i < 4; i++) {
      const digit = s % 10;
      if (digit === 0) {
        if (output) zeroPending = true;
      } else {
        output = `${digits[digit]}${units[i]}${zeroPending ? "零" : ""}${output}`;
        zeroPending = false;
      }
      s = Math.floor(s / 10);
    }
    return output.replace(/零+/g, "零").replace(/零$/g, "");
  }

  let remaining = n;
  let sectionIndex = 0;
  let result = "";
  let needZero = false;

  while (remaining > 0) {
    const sec = remaining % 10000;
    if (sec === 0) {
      if (result) needZero = true;
    } else {
      const secText = sectionToChinese(sec);
      result = `${needZero ? "零" : ""}${secText}${sections[sectionIndex]}${result}`;
      needZero = sec < 1000;
    }
    remaining = Math.floor(remaining / 10000);
    sectionIndex++;
  }

  return `人民币${result.replace(/零+/g, "零").replace(/零$/g, "")}元整`;
}
