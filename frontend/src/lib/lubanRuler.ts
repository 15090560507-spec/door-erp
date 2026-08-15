export interface LubanResult {
  millimeters: number;
  cyclePosition: number;
  bigWord: string;
  smallWord: string;
  auspicious: boolean;
  intervalStart: number;
  intervalEnd: number;
}

export interface LubanContinuousInterval {
  index: number;
  cycleIndex: number;
  intervalIndex: number;
  bigWord: string;
  smallWord: string;
  auspicious: boolean;
  intervalStart: number;
  intervalEnd: number;
}

export interface LubanAdjustment {
  target: number;
  delta: number;
  interval: LubanContinuousInterval;
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

export const LUBAN_SMALL_WORDS = [
  "财德", "宝库", "六合", "迎福",
  "退财", "公事", "牢执", "孤寡",
  "长库", "劫财", "官鬼", "失脱",
  "添丁", "益利", "贵子", "大吉",
  "顺科", "横财", "进益", "富贵",
  "死别", "退口", "离乡", "财失",
  "灾至", "死绝", "病临", "口舌",
  "财至", "登科", "进宝", "兴旺",
] as const;

export const LUBAN_SEGMENT_LENGTH = LUBAN_CYCLE / LUBAN_SMALL_WORDS.length;

export const LUBAN_SMALL_SEGMENTS = LUBAN_SMALL_WORDS.map((smallWord, index) => {
  const bigSection = LUBAN_BIG_SECTIONS[Math.floor(index / 4)];
  return {
    smallWord,
    bigWord: bigSection.name,
    auspicious: bigSection.auspicious,
    intervalStart: index * LUBAN_SEGMENT_LENGTH,
    intervalEnd: (index + 1) * LUBAN_SEGMENT_LENGTH,
  };
});

export function lubanIntervalAtIndex(index: number): LubanContinuousInterval | null {
  if (!Number.isInteger(index) || index < 0) return null;
  const intervalIndex = index % LUBAN_SMALL_WORDS.length;
  const cycleIndex = Math.floor(index / LUBAN_SMALL_WORDS.length);
  const bigSection = LUBAN_BIG_SECTIONS[Math.floor(intervalIndex / 4)];
  return {
    index,
    cycleIndex,
    intervalIndex,
    bigWord: bigSection.name,
    smallWord: LUBAN_SMALL_WORDS[intervalIndex],
    auspicious: bigSection.auspicious,
    intervalStart: index * LUBAN_SEGMENT_LENGTH,
    intervalEnd: (index + 1) * LUBAN_SEGMENT_LENGTH,
  };
}

export function lubanContinuousResult(value: number): LubanContinuousInterval | null {
  if (!Number.isFinite(value) || value < 0) return null;
  return lubanIntervalAtIndex(Math.floor(value / LUBAN_SEGMENT_LENGTH));
}

export function lubanNearbyIntervals(value: number, radius = 4): LubanContinuousInterval[] {
  const current = lubanContinuousResult(value);
  if (!current) return [];
  const safeRadius = Math.max(0, Math.floor(radius));
  const intervals: LubanContinuousInterval[] = [];
  for (let index = Math.max(0, current.index - safeRadius); index <= current.index + safeRadius; index += 1) {
    const interval = lubanIntervalAtIndex(index);
    if (interval) intervals.push(interval);
  }
  return intervals;
}

export function nearestAuspiciousAdjustments(value: number): { down: LubanAdjustment | null; up: LubanAdjustment | null } {
  const current = lubanContinuousResult(value);
  if (!current || current.auspicious) return { down: null, up: null };

  let downInterval: LubanContinuousInterval | null = null;
  for (let index = current.index - 1; index >= 0; index -= 1) {
    const interval = lubanIntervalAtIndex(index);
    if (interval?.auspicious) {
      downInterval = interval;
      break;
    }
  }

  let upInterval: LubanContinuousInterval | null = null;
  for (let index = current.index + 1; index <= current.index + LUBAN_SMALL_WORDS.length; index += 1) {
    const interval = lubanIntervalAtIndex(index);
    if (interval?.auspicious) {
      upInterval = interval;
      break;
    }
  }

  const downTarget = downInterval ? Math.max(0, Math.ceil(downInterval.intervalEnd) - 1) : null;
  const upTarget = upInterval ? Math.ceil(upInterval.intervalStart) : null;
  return {
    down: downInterval && downTarget !== null
      ? { target: downTarget, delta: downTarget - value, interval: downInterval }
      : null,
    up: upInterval && upTarget !== null
      ? { target: upTarget, delta: upTarget - value, interval: upInterval }
      : null,
  };
}

export function lubanResult(value: number): LubanResult | null {
  if (!Number.isFinite(value) || value < 0) return null;
  const cyclePosition = ((value % LUBAN_CYCLE) + LUBAN_CYCLE) % LUBAN_CYCLE;
  const index = Math.min(31, Math.floor(cyclePosition / LUBAN_SEGMENT_LENGTH));
  const bigSection = LUBAN_BIG_SECTIONS[Math.floor(index / 4)];
  return {
    millimeters: value,
    cyclePosition,
    bigWord: bigSection.name,
    smallWord: LUBAN_SMALL_WORDS[index],
    auspicious: bigSection.auspicious,
    intervalStart: index * LUBAN_SEGMENT_LENGTH,
    intervalEnd: (index + 1) * LUBAN_SEGMENT_LENGTH,
  };
}
