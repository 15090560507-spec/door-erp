import type { DoorFormData } from "@/lib/types";

export type DoorAreaMetrics = {
  frameWidth: number;
  frameHeight: number;
  frameArea: number;
  hasFrontOuter: boolean;
  hasInnerTrim: boolean;
  frontOuterWidth: number;
  frontOuterHeight: number;
  backOuterWidth: number;
  backOuterHeight: number;
  outerWidth: number;
  outerHeight: number;
  outerArea: number;
  frontTrimArea: number;
  backTrimArea: number;
  trimArea: number;
};

function numeric(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function calculateDoorAreas(params: DoorFormData): DoorAreaMetrics {
  const frameWidth = numeric(params.dw);
  const frameHeight = numeric(params.dh);
  const hasFrontOuter = Boolean(
    params.has_outer ||
    params.has_outer_portal ||
    params.has_outer_portal2 ||
    params.has_outer_landscape,
  );
  const hasInnerTrim = Boolean(params.has_inner);

  const frontOuterLeftWidth = params.has_outer
    ? numeric(params.trim_front_in)
    : params.has_outer_portal
      ? numeric(params.outer_portal_pillar_width)
      : params.has_outer_portal2
        ? numeric(params.outer_portal2_pillar_width)
        : params.has_outer_landscape
          ? numeric(params.outer_landscape_left_width)
          : 0;
  const frontOuterRightWidth = params.has_outer
    ? numeric(params.trim_front_in)
    : params.has_outer_portal
      ? numeric(params.outer_portal_pillar_width)
      : params.has_outer_portal2
        ? numeric(params.outer_portal2_pillar_width)
        : params.has_outer_landscape
          ? numeric(params.outer_landscape_right_width)
          : 0;
  const frontOuterTopHeight = params.has_outer
    ? numeric(params.trim_front_in)
    : params.has_outer_portal
      ? numeric(params.outer_portal_header_height)
      : params.has_outer_portal2
        ? numeric(params.outer_portal2_header_height)
        : params.has_outer_landscape
          ? numeric(params.outer_landscape_top_height)
          : 0;
  const innerTrimWidth = hasInnerTrim ? numeric(params.trim_back_in) : 0;

  const frontOuterWidth = frameWidth + frontOuterLeftWidth + frontOuterRightWidth;
  const frontOuterHeight = frameHeight + frontOuterTopHeight;
  const backOuterWidth = frameWidth + innerTrimWidth * 2;
  const backOuterHeight = frameHeight + innerTrimWidth;

  // 正面外装饰决定正式外围规格；仅有内包套时才采用反面外围。
  const outerWidth = hasFrontOuter
    ? frontOuterWidth
    : hasInnerTrim
      ? backOuterWidth
      : frameWidth;
  const outerHeight = hasFrontOuter
    ? frontOuterHeight
    : hasInnerTrim
      ? backOuterHeight
      : frameHeight;

  const frameArea = frameWidth > 0 && frameHeight > 0
    ? frameWidth * frameHeight * 0.000001
    : 0;
  const frontTrimArea = hasFrontOuter
    ? Math.max(0, frontOuterWidth * frontOuterHeight * 0.000001 - frameArea)
    : 0;
  const backTrimArea = hasInnerTrim
    ? Math.max(0, backOuterWidth * backOuterHeight * 0.000001 - frameArea)
    : 0;
  const outerArea = outerWidth > 0 && outerHeight > 0
    ? outerWidth * outerHeight * 0.000001
    : 0;

  return {
    frameWidth,
    frameHeight,
    frameArea,
    hasFrontOuter,
    hasInnerTrim,
    frontOuterWidth,
    frontOuterHeight,
    backOuterWidth,
    backOuterHeight,
    outerWidth,
    outerHeight,
    outerArea,
    frontTrimArea,
    backTrimArea,
    trimArea: frontTrimArea + backTrimArea,
  };
}
