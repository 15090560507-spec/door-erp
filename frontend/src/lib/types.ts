// ===================== 用户 =====================
export interface UserInfo {
  uid: string;
  password: string;
  role: string;
  name: string;
  default_module: string;
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
}

// ===================== 表单数据 =====================
export interface DoorFormData {
  dhdw: string;
  gdmc: string;
  ddh: string;
  sl: string;
  hhxd: string;
  dhrq: string;
  zzcl: string;
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
  fw_left_str: string;
  fw_right_str: string;
  fw_top_str: string;
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
  has_inner: boolean;
  overlap: number;
  overlap_front: number;
  overlap_back: number;
  trim_front_in: number;
  trim_back_in: number;
  sel_qc: string;
  qc_shape: string;
  is_integrated_door: boolean;
  integrated_panel_height: number;
  integrated_press_top_rail: number;
  integrated_glass_bottom_rail: number;
  integrated_glass_height: number;
  has_mm: boolean;
  has_pillar: boolean;
  qc_height: number;
  mm_height: number;
  pillar_width_str: string;
  sm: string;
  trim_style_outer: string;
  trim_style_inner: string;
  lock_side_offset?: number;
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
  back_panel_lock_offset_x: number;
  back_panel_hinge_offset_y: number;
  back_panel_middle_offset_z: number;
  back_panel_plus_offset_a: number;
  back_panel_plus_offset_b: number;
  back_panel_three_col_a: number;
  back_panel_three_col_b: number;
  back_panel_three_col_c: number;
  child_panel_lock_offset_x: number;
  child_panel_hinge_offset_y: number;
  child_panel_middle_offset_z: number;
  child_panel_plus_offset_a: number;
  child_panel_plus_offset_b: number;
  child_panel_three_col_a: number;
  child_panel_three_col_b: number;
  child_panel_three_col_c: number;
  left_gap: number;
  right_gap: number;
  top_gap: number;
  bottom_gap: number;
  middle_gap: number;
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
}

export interface TaskListResponse {
  tasks: TaskItem[];
  total: number;
}

// ===================== 模块 =====================
export type ModuleName = "汇总看板" | "图纸信息录入" | "图纸绘制" | "图纸初审" | "图纸终审" | "报价系统" | "后台管理";

// ===================== 状态常量 =====================
export const MODULE_OPTIONS: { title: string; module: ModuleName }[] = [
  { title: "汇总看板", module: "汇总看板" },
  { title: "图纸信息录入", module: "图纸信息录入" },
  { title: "图纸绘制", module: "图纸绘制" },
  { title: "图纸初审", module: "图纸初审" },
  { title: "图纸终审", module: "图纸终审" },
  { title: "报价系统", module: "报价系统" },
];

export const DOOR_TYPES = ["单门", "对开门", "子母门", "两定两开", "折叠四开门"];
export const KX_OPTIONS = ["左开", "右开"];
export const NK_OPTIONS = ["内开", "外开"];
export const THRESHOLD_OPTIONS = ["高低槛", "平底槛", "吊脚"];
export const QC_OPTIONS = ["无", "玻璃", "封闭"];
export const QC_SHAPE_OPTIONS = ["矩形气窗", "弧形气窗"];
export const BZ_OPTIONS = ["全包", "木箱"];
export const HYSL_OPTIONS = ["3个/扇", "2个/扇", "4个/扇", "5个/扇"];
export const MATERIALS = ["0.8的不锈钢镀铜", "1.0的不锈钢镀铜", "1.2的不锈钢镀铜", "0.8的纯铜", "1.0的纯铜", "1.2的纯铜", "纯铝"];
export const HANDLES = ["标配拉手", "A1022", "铝雕拉手", "铝雕滑盖拉手", "铝雕长拉手", "自制长拉手", "背包拉手"];
export const LOCKS = ["连体锁", "标准锁体", "防盗锁体", "霸王锁体", "快装锁体"];
export const FINGERPRINT_LOCKS = ["", "安志杰AF-12", "Q3指纹锁", "T5指纹锁", "客备指纹锁"];
export const HINGES = ["葫芦头合页", "可拆卸合页", "三维可调合页", "暗合页", "北京暗合页", "明合页暗装", "明合页"];
export const COLOR_PRESETS = ["2号色", "2.3号色", "2.5号色", "3号色", "6号色乱纹", "7号色乱纹"];
export const TRIM_STYLES = ["平包套", "斜包套", "阶梯包套", "工字形包套", "01款包套", "02款包套"];
export const DOOR_PANEL_STYLES = ["无造型", "两列式布局", "三列式布局", "H型布局", "H+型布局"];

export const DEFAULT_FORM_DATA: DoorFormData = {
  dhdw: "", gdmc: "", ys: "2号色", zzcl: "0.8的不锈钢镀铜",
  zmks: "按图", fmks: "按图",
  zmls: "标配拉手", fmls: "标配拉手", handle_size: "", st_val: "连体锁", fingerprint_lock: "",
  hysl: "3个/扇", sel_hys: "", qh: "", mshd: 80,
  sm: "", trim_style_outer: "", trim_style_inner: "", lock_side_offset: 0,
  door_panel_style: "无造型", back_door_panel_style: "无造型", child_door_panel_style: "",
  panel_lock_offset_x: 180, panel_hinge_offset_y: 100,
  panel_middle_offset_z: 180, panel_plus_offset_a: 350, panel_plus_offset_b: 100,
  panel_three_col_a: 180, panel_three_col_b: 0, panel_three_col_c: 100,
  back_panel_lock_offset_x: 180, back_panel_hinge_offset_y: 100,
  back_panel_middle_offset_z: 180, back_panel_plus_offset_a: 350, back_panel_plus_offset_b: 100,
  back_panel_three_col_a: 180, back_panel_three_col_b: 0, back_panel_three_col_c: 100,
  child_panel_lock_offset_x: 180, child_panel_hinge_offset_y: 100,
  child_panel_middle_offset_z: 180, child_panel_plus_offset_a: 350, child_panel_plus_offset_b: 100,
  child_panel_three_col_a: 180, child_panel_three_col_b: 0, child_panel_three_col_c: 100,
  ddh: "", sl: "1 樘", hhxd: "D",
  dhrq: new Date().toISOString().slice(0, 10),
  door_type: "单门", mother_door_width: 600, mid_door_width: 400,
  has_pillar: false, pillar_width_str: "55/70",
  sel_kx: "右开", sel_nk: "内开",
  sel_qc: "无", qc_shape: "矩形气窗", qc_height: 400,
  is_integrated_door: false, integrated_panel_height: 300,
  integrated_press_top_rail: 20, integrated_glass_bottom_rail: 20,
  integrated_glass_height: 500,
  has_mm: false, mm_height: 200,
  has_outer: true, trim_front_in: 160,
  has_inner: false, trim_back_in: 140,
  dw: 900, dh: 2100, overlap: 20, overlap_front: 20, overlap_back: 20,
  fw_left_str: "55/85", fw_right_str: "55/62", fw_top_str: "55/75",
  th_str: "55/75", threshold_type: "高低槛", has_dj: false, dj_height: 0,
  left_gap: 2, right_gap: 2, top_gap: 3, bottom_gap: 5, middle_gap: 4,
  use_light_size: false, mark_light_size: false, light_w: 0, light_h: 0,
  pdk: "60", sel_bz: "全包",
};
