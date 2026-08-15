export interface LubanResult {
  millimeters: number;
  cyclePosition: number;
  bigWord: string;
  smallWord: string;
  auspicious: boolean;
  intervalStart: number;
  intervalEnd: number;
}

export const LUBAN_CYCLE = 429;
export const LUBAN_BIG_SECTIONS = [
  { name: "财", auspicious: true },
  { name: "病", auspicious: false },
  { name: "离", auspicious: false },
  { name: "义", auspicious: true },
  { name: "官", auspicious: true },
  { name: "劫", auspicious: false },
  { name: "害", auspicious: false },
  { name: "本", auspicious: true },
] as const;

const SMALL_WORDS = [
  "财德", "宝库", "六合", "迎福",
  "退财", "公事", "牢执", "孤寡",
  "长库", "劫财", "官鬼", "失脱",
  "添丁", "益利", "贵子", "大吉",
  "顺科", "横财", "进益", "富贵",
  "死别", "退口", "离乡", "财失",
  "灾至", "死绝", "病临", "口舌",
  "财至", "登科", "进宝", "兴旺",
] as const;

export function lubanResult(value: number): LubanResult | null {
  if (!Number.isFinite(value) || value < 0) return null;
  const cyclePosition = ((value % LUBAN_CYCLE) + LUBAN_CYCLE) % LUBAN_CYCLE;
  const segmentLength = LUBAN_CYCLE / 32;
  const index = Math.min(31, Math.floor(cyclePosition / segmentLength));
  const bigSection = LUBAN_BIG_SECTIONS[Math.floor(index / 4)];
  return {
    millimeters: value,
    cyclePosition,
    bigWord: bigSection.name,
    smallWord: SMALL_WORDS[index],
    auspicious: bigSection.auspicious,
    intervalStart: index * segmentLength,
    intervalEnd: (index + 1) * segmentLength,
  };
}
