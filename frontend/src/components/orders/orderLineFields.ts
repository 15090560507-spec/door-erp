import type { SalesOrderTechnicalDetails } from "@/lib/salesOrderTypes";

export interface OrderLineTechnicalField {
  key: keyof SalesOrderTechnicalDetails;
  label: string;
  fallbackKeys: readonly string[];
}

export const ORDER_LINE_TECHNICAL_FIELDS = [
  { key: "trim_type", label: "门套类型", fallbackKeys: ["trim_type", "trim_style_outer", "sel_bz"] },
  { key: "main_door_style", label: "主门款式", fallbackKeys: ["main_door_style", "zmks"] },
  { key: "lock_type", label: "锁具", fallbackKeys: ["lock_type", "fingerprint_lock", "st_val"] },
  { key: "handle", label: "拉手", fallbackKeys: ["handle", "zmls"] },
  { key: "hinge", label: "铰链", fallbackKeys: ["hinge", "sel_hys"] },
  { key: "material", label: "材质", fallbackKeys: ["material", "zzcl"] },
  { key: "item_remark", label: "商品行备注", fallbackKeys: ["item_remark"] },
] as const satisfies readonly OrderLineTechnicalField[];
