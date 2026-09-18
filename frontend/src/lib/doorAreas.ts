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

function numericOr(value: unknown, fallback: unknown): number {
  return value === undefined || value === null ? numeric(fallback) : numeric(value);
}

function exposedSize(width: unknown, overlap: unknown): number {
  return Math.max(0, numeric(width) - numeric(overlap));
}

function selectedSection(value: unknown, opening: unknown, fallback = 0): number {
  const values = String(value ?? "")
    .split("/")
    .map((part) => Number(part.trim()))
    .filter(Number.isFinite);
  if (!values.length) return fallback;
  return String(opening || "").includes("内开")
    ? Math.max(...values)
    : Math.min(...values);
}

export function resolveFrameDimensions(params: DoorFormData): { width: number; height: number } {
  const stored = { width: numeric(params.dw), height: numeric(params.dh) };
  if (!params.use_light_size) return stored;

  const lightWidth = numeric(params.light_w);
  const lightHeight = numeric(params.light_h);
  if (lightWidth <= 0 || lightHeight <= 0) return stored;

  const left = selectedSection(params.fw_left_str, params.sel_nk);
  const right = selectedSection(params.fw_right_str, params.sel_nk);
  const top = selectedSection(params.fw_top_str, params.sel_nk);
  const bottom = params.threshold_type === "吊脚" || params.has_dj
    ? 0
    : params.threshold_type === "平底槛"
      ? numeric(params.pdk)
      : selectedSection(params.th_str, params.sel_nk);

  return {
    width: Math.max(300, lightWidth + left + right),
    height: Math.max(600, lightHeight + top + bottom),
  };
}

export function calculateDoorAreas(params: DoorFormData): DoorAreaMetrics {
  const resolvedFrame = resolveFrameDimensions(params);
  const frameWidth = resolvedFrame.width;
  const baseFrameHeight = resolvedFrame.height;
  // CAD treats dh as the door portion below the transom; quoting uses the full frame height.
  const hasTransom = ["玻璃", "封闭"].includes(String(params.sel_qc || "").trim());
  const transomHeight = hasTransom ? Math.max(0, numeric(params.qc_height)) : 0;
  const frameHeight = baseFrameHeight + transomHeight;
  const hasFrontOuter = Boolean(
    params.has_outer ||
    params.has_outer_portal ||
    params.has_outer_portal2 ||
    params.has_outer_landscape,
  );
  const hasInnerTrim = Boolean(params.has_inner);

  const frontOverlapLr = numericOr(params.overlap_front_lr, params.overlap_front);
  const frontOverlapTop = numericOr(params.overlap_front_top, params.overlap_front);
  const backOverlapLr = numericOr(params.overlap_back_lr, params.overlap_back);
  const backOverlapTop = numericOr(params.overlap_back_top, params.overlap_back);

  const frontOuterLeftWidth = params.has_outer
    ? exposedSize(params.trim_front_in, frontOverlapLr)
    : params.has_outer_portal
      ? exposedSize(params.outer_portal_pillar_width, frontOverlapLr)
      : params.has_outer_portal2
        ? exposedSize(params.outer_portal2_pillar_width, params.outer_portal2_lr_overlap)
        : params.has_outer_landscape
          ? exposedSize(params.outer_landscape_left_width, params.outer_landscape_left_overlap)
          : 0;
  const frontOuterRightWidth = params.has_outer
    ? exposedSize(params.trim_front_in, frontOverlapLr)
    : params.has_outer_portal
      ? exposedSize(params.outer_portal_pillar_width, frontOverlapLr)
      : params.has_outer_portal2
        ? exposedSize(params.outer_portal2_pillar_width, params.outer_portal2_lr_overlap)
        : params.has_outer_landscape
          ? exposedSize(params.outer_landscape_right_width, params.outer_landscape_right_overlap)
          : 0;
  const frontOuterTopHeight = params.has_outer
    ? exposedSize(params.trim_front_in, frontOverlapTop)
    : params.has_outer_portal
      ? exposedSize(params.outer_portal_header_height, frontOverlapTop)
      : params.has_outer_portal2
        ? exposedSize(params.outer_portal2_header_height, params.outer_portal2_top_overlap)
        : params.has_outer_landscape
          ? exposedSize(params.outer_landscape_top_height, params.outer_landscape_top_overlap)
          : 0;
  const innerTrimSide = hasInnerTrim
    ? exposedSize(params.trim_back_in, backOverlapLr)
    : 0;
  const innerTrimTop = hasInnerTrim
    ? exposedSize(params.trim_back_in, backOverlapTop)
    : 0;

  const frontOuterWidth = frameWidth + frontOuterLeftWidth + frontOuterRightWidth;
  const frontOuterHeight = frameHeight + frontOuterTopHeight;
  const backOuterWidth = frameWidth + innerTrimSide * 2;
  const backOuterHeight = frameHeight + innerTrimTop;

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
