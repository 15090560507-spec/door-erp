import type { DoorAreaMetrics } from "./doorAreas";
import type { QuoteItem, QuoteTrimMetrics } from "./quoteTypes";

export const DEFAULT_EXTRA_TRIM_FACTOR = 0.7;

export function outerQuoteBasis(areas: DoorAreaMetrics, metrics: QuoteTrimMetrics | null) {
  if (!areas.hasFrontOuter || !areas.hasInnerTrim) {
    return { width: areas.outerWidth, height: areas.outerHeight,
      side: areas.hasFrontOuter ? "outer" : areas.hasInnerTrim ? "inner" : "frame", extra: null };
  }
  const outer = metrics?.outer, inner = metrics?.inner;
  if (!outer?.valid || !inner?.valid || !outer.outerBounds || !inner.outerBounds) {
    throw new Error("内外门套轮廓不可用，请检查图纸后重新关联，未生成不完整报价");
  }
  for (const side of [outer, inner]) {
    const bounds = side.outerBounds!;
    if (![bounds.width, bounds.height].every(value => Number.isFinite(value) && value > 0)
      || !Number.isFinite(side.quoteArea) || side.quoteArea < 0) {
      throw new Error("门套尺寸或净面积无效，请检查图纸");
    }
  }
  const innerIsLarger = inner.outerBounds.width * inner.outerBounds.height
    > outer.outerBounds.width * outer.outerBounds.height + 0.000001;
  const main = innerIsLarger ? inner : outer;
  const extra = innerIsLarger ? outer : inner;
  return { width: main.outerBounds!.width, height: main.outerBounds!.height,
    side: main.side, extra: { side: extra.side, netArea: Number(extra.quoteArea.toFixed(4)) } };
}

export function linkExtraTrimPrices(items: QuoteItem[], factor: number): QuoteItem[] {
  const main = items.find(item => item.pricingRole === "mainDoor");
  if (!main) return items;
  const unitPrice = Number((Number(main.unitPrice || 0) * factor).toFixed(2));
  return items.map(item => item.pricingRole === "extraTrim" ? { ...item, unitPrice } : item);
}

export function editOuterQuoteRows(previous: QuoteItem[], next: QuoteItem[], factor: number) {
  const main = next.find(item => item.pricingRole === "mainDoor");
  const oldMain = previous.find(item => item.pricingRole === "mainDoor");
  const extra = next.find(item => item.pricingRole === "extraTrim");
  const oldExtra = previous.find(item => item.pricingRole === "extraTrim");
  const nextFactor = main && oldMain && extra && oldExtra && main.unitPrice > 0
    && main.unitPrice === oldMain.unitPrice && extra.unitPrice !== oldExtra.unitPrice
    ? Number((extra.unitPrice / main.unitPrice).toFixed(6)) : factor;
  return { items: linkExtraTrimPrices(next, nextFactor), factor: nextFactor };
}
