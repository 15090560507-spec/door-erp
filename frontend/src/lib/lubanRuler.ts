export type LubanRulerKind = "regular" | "gugong";

export interface LubanRulerVersion {
  key: LubanRulerKind;
  label: string;
  cycle: number;
  description: string;
}

export const LUBAN_RULER_VERSIONS: LubanRulerVersion[] = [
  { key: "regular", label: "常规鲁班尺", cycle: 429, description: "429mm 周期" },
  { key: "gugong", label: "故宫鲁班尺", cycle: 460.8, description: "460.8mm 周期" },
];

export const DEFAULT_LUBAN_RULER_KIND: LubanRulerKind = "regular";

export function lubanRulerVersion(kind: LubanRulerKind): LubanRulerVersion {
  return LUBAN_RULER_VERSIONS.find((version) => version.key === kind) ?? LUBAN_RULER_VERSIONS[0];
}

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

export function lubanSegmentLength(kind: LubanRulerKind): number {
  return lubanRulerVersion(kind).cycle / LUBAN_SMALL_WORDS.length;
}

export function lubanIntervalAtIndex(index: number, kind: LubanRulerKind): LubanContinuousInterval | null {
  if (!Number.isInteger(index) || index < 0) return null;
  const segmentLength = lubanSegmentLength(kind);
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
    intervalStart: index * segmentLength,
    intervalEnd: (index + 1) * segmentLength,
  };
}

export function lubanContinuousResult(value: number, kind: LubanRulerKind = DEFAULT_LUBAN_RULER_KIND): LubanContinuousInterval | null {
  if (!Number.isFinite(value) || value < 0) return null;
  return lubanIntervalAtIndex(Math.floor(value / lubanSegmentLength(kind)), kind);
}

export function lubanNearbyIntervals(value: number, radius = 4, kind: LubanRulerKind = DEFAULT_LUBAN_RULER_KIND): LubanContinuousInterval[] {
  const current = lubanContinuousResult(value, kind);
  if (!current) return [];
  const safeRadius = Math.max(0, Math.floor(radius));
  const intervals: LubanContinuousInterval[] = [];
  for (let index = Math.max(0, current.index - safeRadius); index <= current.index + safeRadius; index += 1) {
    const interval = lubanIntervalAtIndex(index, kind);
    if (interval) intervals.push(interval);
  }
  return intervals;
}

export function nearestAuspiciousAdjustments(value: number, kind: LubanRulerKind = DEFAULT_LUBAN_RULER_KIND): { down: LubanAdjustment | null; up: LubanAdjustment | null } {
  const current = lubanContinuousResult(value, kind);
  if (!current || current.auspicious) return { down: null, up: null };

  let downInterval: LubanContinuousInterval | null = null;
  for (let index = current.index - 1; index >= 0; index -= 1) {
    const interval = lubanIntervalAtIndex(index, kind);
    if (interval?.auspicious) {
      downInterval = interval;
      break;
    }
  }

  let upInterval: LubanContinuousInterval | null = null;
  for (let index = current.index + 1; index <= current.index + LUBAN_SMALL_WORDS.length; index += 1) {
    const interval = lubanIntervalAtIndex(index, kind);
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

export function lubanResult(value: number, kind: LubanRulerKind = DEFAULT_LUBAN_RULER_KIND): LubanResult | null {
  if (!Number.isFinite(value) || value < 0) return null;
  const cycle = lubanRulerVersion(kind).cycle;
  const segmentLength = lubanSegmentLength(kind);
  const cyclePosition = ((value % cycle) + cycle) % cycle;
  const index = Math.min(LUBAN_SMALL_WORDS.length - 1, Math.floor(cyclePosition / segmentLength));
  const bigSection = LUBAN_BIG_SECTIONS[Math.floor(index / 4)];
  return {
    millimeters: value,
    cyclePosition,
    bigWord: bigSection.name,
    smallWord: LUBAN_SMALL_WORDS[index],
    auspicious: bigSection.auspicious,
    intervalStart: index * segmentLength,
    intervalEnd: (index + 1) * segmentLength,
  };
}
