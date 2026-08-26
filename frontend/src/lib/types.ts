import { localDateYmd } from "./dateTime";

// ===================== 用户 =====================
export interface UserInfo {
  uid: string;
  role: string;
  name: string;
  default_module: string;
  permissions: string[];
}

export interface LoginResponse {
  success: boolean;
  message: string;
  user?: UserInfo;
  token?: string;
}

export interface VerifyResponse {
  uid: string;
  role: string;
  name: string;
  default_module: string;
  permissions: string[];
}

// ===================== 表单数据 =====================
export interface DoorFormData {
  dhdw: string;
  gdmc: string;
  ddh: string;
  sl: string;
  hhxd: string;
  dhrq: string;
  /** 旧任务兼容字段，新任务由 material + product_name 组合生成。 */
  zzcl: string;
  material: string;
  product_name: string;
  order_title: string;
  ys: string;
  zmks: string;
  fmks: string;
  mshd: number;
  qh: string;
  sel_bz: string;
  door_type: string;
  sel_kx: string;
  sel_nk: string;
  use_light_size: boolean;
  mark_light_size: boolean;
  dw: number;
  dh: number;
  light_w: number;
  light_h: number;
  mother_door_width: number;
  mid_door_width: number;
  mid_clear_width: number;
  sliding_overlap: number;
  fw_left_str: string;
  fw_right_str: string;
  fw_top_str: string;
  frame_process: string;
  new_frame_settings: Record<string, string | number | boolean>;
  old_frame_settings: Record<string, string | number | boolean>;
  threshold_type: string;
  th_str: string;
  pdk: string;
  has_dj: boolean;
  dj_height: number;
  zmls: string;
  fmls: string;
  handle_size: string;
  st_val: string;
  fingerprint_lock: string;
  sel_hys: string;
  hysl: string;
  has_outer: boolean;
  has_outer_portal: boolean;
  has_outer_portal2: boolean;
  has_outer_landscape: boolean;
  has_inner: boolean;
  overlap: number;
  overlap_front: number;
  overlap_back: number;
  overlap_front_lr: number;
  overlap_front_top: number;
  overlap_back_lr: number;
  overlap_back_top: number;
  trim_front_in: number;
  outer_portal_pillar_width: number;
  outer_portal_header_height: number;
  outer_portal2_pillar_width: number;
  outer_portal2_header_height: number;
  outer_portal2_lr_overlap: number;
  outer_portal2_top_overlap: number;
  outer_landscape_left_width: number;
  outer_landscape_right_width: number;
  outer_landscape_top_height: number;
  outer_landscape_left_overlap: number;
  outer_landscape_right_overlap: number;
  outer_landscape_top_overlap: number;
  trim_back_in: number;
  sel_qc: string;
  qc_shape: string;
  glass_spec: string;
  is_arch_door: boolean;
  arch_spring_height: number;
  is_integrated_door: boolean;
  integrated_panel_height: number;
  integrated_press_top_rail: number;
  integrated_glass_bottom_rail: number;
  integrated_glass_height: number;
  has_mm: boolean;
  has_pillar: boolean;
  qc_height: number;
  qc_glass_style: string;
  mm_height: number;
  pillar_width_str: string;
  sm: string;
  trim_style_outer: string;
  trim_style_inner: string;
  lock_side_offset?: number;
  panel_preset: string;
  door_panel_style: string;
  back_door_panel_style: string;
  child_door_panel_style: string;
  panel_lock_offset_x: number;
  panel_hinge_offset_y: number;
  panel_middle_offset_z: number;
  panel_plus_offset_a: number;
  panel_plus_offset_b: number;
  panel_three_col_a: number;
  panel_three_col_b: number;
  panel_three_col_c: number;
  panel_fill_a: string;
  panel_fill_b: string;
  panel_fill_c: string;
  panel_disc_radius: number;
  panel_horizontal_a_height: number;
  panel_horizontal_b_height: number;
  panel_b2_glass_style: string;
  panel_b4_glass_style: string;
  back_panel_lock_offset_x: number;
  back_panel_hinge_offset_y: number;
  back_panel_middle_offset_z: number;
  back_panel_plus_offset_a: number;
  back_panel_plus_offset_b: number;
  back_panel_three_col_a: number;
  back_panel_three_col_b: number;
  back_panel_three_col_c: number;
  back_panel_fill_a: string;
  back_panel_fill_b: string;
  back_panel_fill_c: string;
  back_panel_disc_radius: number;
  back_panel_horizontal_a_height: number;
  back_panel_horizontal_b_height: number;
  back_panel_b2_glass_style: string;
  back_panel_b4_glass_style: string;
  child_panel_lock_offset_x: number;
  child_panel_hinge_offset_y: number;
  child_panel_middle_offset_z: number;
  child_panel_plus_offset_a: number;
  child_panel_plus_offset_b: number;
  child_panel_three_col_a: number;
  child_panel_three_col_b: number;
  child_panel_three_col_c: number;
  child_panel_fill_a: string;
  child_panel_fill_b: string;
  child_panel_fill_c: string;
  child_panel_disc_radius: number;
  child_panel_horizontal_a_height: number;
  child_panel_horizontal_b_height: number;
  child_panel_b2_glass_style: string;
  child_panel_b4_glass_style: string;
  glass_line_inset: number;
  glass_line_spacing: number;
  back_glass_line_inset: number;
  back_glass_line_spacing: number;
  left_gap: number;
  right_gap: number;
  top_gap: number;
  bottom_gap: number;
  middle_gap: number;
  enable_occlusion: boolean;
}

// ===================== 任务 =====================
export interface ChangeEntry {
  field: string;
  old: string;
  new: string;
}

export interface HistoryEntry {
  modified_by: string;
  modified_at: string;
  changes: ChangeEntry[];
}

export interface TaskItem {
  id: string;
  date: string;
  status: string;
  customer: string;
  project: string;
  door_type: string;
  size: string;
  params: DoorFormData;
  ref_text: string;
  ref_images: string[];
  drawing_img_b64: string | null;
  review_feedback: string;
  history: HistoryEntry[];
  quote_status?: string;
  confirm_status?: string;
}

export interface TaskListResponse {
  tasks: TaskItem[];
  total: number;
}

// ===================== 分层效果图 =====================
export interface LayeredRenderFile {
  url: string;
  originalName: string;
}

export interface LayeredRenderRecord {
  id: string;
  taskId: string;
  customer: string;
  faces: string;
  dpi: number;
  targetLongEdge: number;
  canvasSize: [number, number];
  files: {
    psd: LayeredRenderFile;
    complete: LayeredRenderFile;
    front: LayeredRenderFile;
    back: LayeredRenderFile;
  };
  materialMode?: "ai" | "flat";
  materialNote?: string;
  modelConfig?: { name?: string; provider?: string; model?: string };
  createdAt: string;
  version: number;
}

// ===================== 模块 =====================
export type ModuleName = "图纸信息录入" | "图纸绘制" | "图纸初审" | "报价系统" | "效果渲染" | "图纸终审" | "任务总览" | "生产管理";

// ===================== 状态常量 =====================
export const MODULE_OPTIONS: { title: string; module: ModuleName }[] = [
  { title: "图纸信息录入", module: "图纸信息录入" },
  { title: "图纸绘制", module: "图纸绘制" },
  { title: "图纸初审", module: "图纸初审" },
  { title: "图纸终审", module: "图纸终审" },
  { title: "效果渲染", module: "效果渲染" },
  { title: "报价系统", module: "报价系统" },
  { title: "生产管理", module: "生产管理" },
  { title: "任务总览", module: "任务总览" },
];

export const DOOR_TYPES = ["单门", "对开门", "子母门", "两定两开", "四开门"];
export const KX_OPTIONS = ["左开", "右开"];
export const NK_OPTIONS = ["内开", "外开"];
export const THRESHOLD_OPTIONS = ["高低槛", "平底槛", "吊脚"];
export const QC_OPTIONS = ["无", "玻璃", "封闭"];
export const QC_SHAPE_OPTIONS = ["矩形气窗", "弧形气窗"];
export const BZ_OPTIONS = ["全包", "木箱"];
export const HYSL_OPTIONS = ["2个/扇", "3个/扇", "4个/扇", "5个/扇", "1套/扇", "1套/樘"];
export const MATERIALS = [
  "0.8的不锈钢镀铜",
  "1.0的不锈钢镀铜",
  "1.2的不锈钢镀铜",
  "0.8的201不锈钢镀铜",
  "1.0的201不锈钢镀铜",
  "1.2的201不锈钢镀铜",
  "0.8的304不锈钢镀铜",
  "1.0的304不锈钢镀铜",
  "1.2的304不锈钢镀铜",
  "0.8的不锈钢镀铜木纹板",
  "1.0的不锈钢镀铜木纹板",
  "1.2的不锈钢镀铜木纹板",
  "0.8的304不锈钢镀铜木纹板",
  "1.0的304不锈钢镀铜木纹板",
  "1.2的304不锈钢镀铜木纹板",
];
export const MATERIAL_THICKNESSES = ["0.8mm", "1.0mm", "1.2mm", "1.5mm", "2.0mm"];
export const PRODUCT_NAMES = ["不锈钢镀铜门", "纯铜门", "全铝门", "庭院门", "系统门", "平移门", "地弹簧门", "天弹簧门", "铝艺栅栏", "雨棚", "牌匾", "其他"];
export const ORDER_TITLES = ["浙江西州将军铜门订货单", "杭州兰庭新贵门业"];
export const HANDLES = ["标配拉手", "A1022", "A635", "分体拉手", "铝雕拉手", "铝雕滑盖拉手", "铝雕长拉手", "自制长拉手", "背包拉手", "凹槽拉手", "凹槽拉手+灯带"];
export const LOCKS = ["连体锁", "霸王锁体", "标准锁体", "磁力锁", "暗装磁力锁"];
export const FINGERPRINT_LOCKS = ["", "无", "安志杰AF-12", "Q3指纹锁", "T5指纹锁", "客备指纹锁"];
export const HINGES = [
  "葫芦头合页", "可拆卸合页", "三维可调合页", "暗合页", "半钢暗合页", "全钢暗合页",
  "北京暗合页", "明合页暗装", "明合页", "电动开门机", "地弹簧", "天弹簧", "天地轴", "明合页+闭门器",
];
export const GLASS_SPECS = ["10mm钢化玻璃", "10mm钢化超白玻璃", "10mm夹胶玻璃", "10mm普通白玻", "5+12+5中空钢化玻璃"];
export const COLOR_PRESETS = ["2号色", "2.3号色", "2.5号色", "3号色", "6号色乱纹", "7号色乱纹"];
export const TRIM_STYLES = ["平包套", "斜包套", "阶梯包套", "工字形包套", "01款包套", "02款包套", "03款包套"];
export const DOOR_STYLES = ["平板"];
export const DOOR_PANEL_STYLES = ["无造型", "大板布局", "两列式布局", "三列式布局", "两横式", "三横式", "H型布局", "H+型布局", "圆盘造型"];
export const DOOR_PANEL_PRESETS = ["", "紫荆花款", "钱币款", "竖条款", "流星雨款", "四方纳福款"];
export const PANEL_FILL_OPTIONS = ["", "紫荆花", "钱币款", "流星雨", "四方纳福", "竖条", "斜实虚", "正实虚"];
export const GLASS_LINE_STYLES = ["无线条", "单圈外围线", "单圈外围线(封闭)", "四角回纹", "双边框", "双边框+花件", "六格线条", "八格线条"];

export const DEFAULT_FORM_DATA: DoorFormData = {
  dhdw: "", gdmc: "", ys: "2号色", zzcl: "", material: "0.8mm", product_name: "不锈钢镀铜门", order_title: "浙江西州将军铜门订货单",
  zmks: "", fmks: "",
  zmls: "标配拉手", fmls: "标配拉手", handle_size: "", st_val: "", fingerprint_lock: "",
  hysl: "3个/扇", sel_hys: "", qh: "", mshd: 80,
  sm: "", trim_style_outer: "", trim_style_inner: "", lock_side_offset: 0, panel_preset: "",
  door_panel_style: "无造型", back_door_panel_style: "无造型", child_door_panel_style: "",
  panel_lock_offset_x: 180, panel_hinge_offset_y: 100,
  panel_middle_offset_z: 180, panel_plus_offset_a: 350, panel_plus_offset_b: 100,
  panel_three_col_a: 180, panel_three_col_b: 0, panel_three_col_c: 100,
  panel_fill_a: "", panel_fill_b: "", panel_fill_c: "", panel_disc_radius: 120,
  panel_horizontal_a_height: 1000, panel_horizontal_b_height: 300, panel_b2_glass_style: "无线条", panel_b4_glass_style: "无线条",
  back_panel_lock_offset_x: 180, back_panel_hinge_offset_y: 100,
  back_panel_middle_offset_z: 180, back_panel_plus_offset_a: 350, back_panel_plus_offset_b: 100,
  back_panel_three_col_a: 180, back_panel_three_col_b: 0, back_panel_three_col_c: 100,
  back_panel_fill_a: "", back_panel_fill_b: "", back_panel_fill_c: "", back_panel_disc_radius: 120,
  back_panel_horizontal_a_height: 1000, back_panel_horizontal_b_height: 300, back_panel_b2_glass_style: "无线条", back_panel_b4_glass_style: "无线条",
  child_panel_lock_offset_x: 180, child_panel_hinge_offset_y: 100,
  child_panel_middle_offset_z: 180, child_panel_plus_offset_a: 350, child_panel_plus_offset_b: 100,
  child_panel_three_col_a: 180, child_panel_three_col_b: 0, child_panel_three_col_c: 100,
  child_panel_fill_a: "", child_panel_fill_b: "", child_panel_fill_c: "", child_panel_disc_radius: 120,
  child_panel_horizontal_a_height: 1000, child_panel_horizontal_b_height: 300, child_panel_b2_glass_style: "无线条", child_panel_b4_glass_style: "无线条",
  glass_line_inset: 20, glass_line_spacing: 20, back_glass_line_inset: 0, back_glass_line_spacing: 0,
  ddh: "", sl: "1 樘", hhxd: "D",
  dhrq: localDateYmd(),
  door_type: "单门", mother_door_width: 600, mid_door_width: 400, mid_clear_width: 0, sliding_overlap: 45,
  has_pillar: false, pillar_width_str: "55/85",
  sel_kx: "右开", sel_nk: "内开",
  sel_qc: "无", qc_shape: "矩形气窗", glass_spec: "", qc_height: 400, qc_glass_style: "无线条",
  is_arch_door: false, arch_spring_height: 1800,
  is_integrated_door: false, integrated_panel_height: 300,
  integrated_press_top_rail: 20, integrated_glass_bottom_rail: 20,
  integrated_glass_height: 500,
  has_mm: false, mm_height: 200,
  has_outer: true, has_outer_portal: false, has_outer_portal2: false, has_outer_landscape: false, trim_front_in: 160,
  outer_portal_pillar_width: 160, outer_portal_header_height: 220,
  outer_portal2_pillar_width: 160, outer_portal2_header_height: 220,
  outer_portal2_lr_overlap: 20, outer_portal2_top_overlap: 20,
  outer_landscape_left_width: 160, outer_landscape_right_width: 160, outer_landscape_top_height: 160,
  outer_landscape_left_overlap: 20, outer_landscape_right_overlap: 20, outer_landscape_top_overlap: 20,
  has_inner: false, trim_back_in: 140,
  dw: 900, dh: 2100, overlap: 20, overlap_front: 20, overlap_back: 20,
  overlap_front_lr: 20, overlap_front_top: 20, overlap_back_lr: 20, overlap_back_top: 20,
  fw_left_str: "55/85", fw_right_str: "55/62", fw_top_str: "55/75",
  frame_process: "新工艺", new_frame_settings: {}, old_frame_settings: {},
  th_str: "55/75", threshold_type: "高低槛", has_dj: false, dj_height: 0,
  left_gap: 2, right_gap: 2, top_gap: 3, bottom_gap: 5, middle_gap: 2,
  enable_occlusion: false,
  use_light_size: false, mark_light_size: false, light_w: 0, light_h: 0,
  pdk: "60", sel_bz: "全包",
};
