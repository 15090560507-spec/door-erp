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
  zmls: string;
  fmls: string;
  st_val: string;
  sel_hys: string;
  hysl: string;
  has_outer: boolean;
  has_inner: boolean;
  overlap: number;
  trim_front_in: number;
  trim_back_in: number;
  sel_qc: string;
  has_mm: boolean;
  has_pillar: boolean;
  qc_height: number;
  mm_height: number;
  pillar_width_str: string;
  sm: string;
  trim_style_outer: string;
  trim_style_inner: string;
  lock_side_offset: number;
  left_gap: number;
  right_gap: number;
  top_gap: number;
  bottom_gap: number;
  middle_gap: number;
}

// ===================== 任务 =====================
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
  ref_img_b64: string | null;
  drawing_img_b64: string | null;
  review_feedback: string;
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
export const THRESHOLD_OPTIONS = ["高低槛", "平底槛"];
export const QC_OPTIONS = ["无", "玻璃", "封闭"];
export const BZ_OPTIONS = ["全包", "木箱"];
export const HYSL_OPTIONS = ["3个/扇", "2个/扇", "4个/扇", "5个/扇"];
export const MATERIALS = ["0.8的不锈钢镀铜", "1.0的不锈钢镀铜", "1.2的不锈钢镀铜", "0.8的纯铜", "1.0的纯铜", "1.2的纯铜", "纯铝"];
export const HANDLES = ["标配拉手", "铝雕拉手", "铝雕滑盖拉手", "铝雕长拉手", "自制长拉手", "背包拉手"];
export const LOCKS = ["标准锁体", "防盗锁体", "霸王锁体", "快装锁体"];
export const HINGES = ["葫芦头合页", "可拆卸合页", "暗合页", "明合页暗装", "明合页"];
export const COLOR_PRESETS = ["2号色", "2.3号色", "2.5号色", "3号色", "6号色乱纹", "7号色乱纹"];
export const TRIM_STYLES = ["斜包套", "阶梯包套", "工字形包套", "01款包套", "02款包套"];

export const DEFAULT_FORM_DATA: DoorFormData = {
  dhdw: "", gdmc: "", ys: "2号色", zzcl: "0.8的不锈钢镀铜",
  zmks: "按图", fmks: "按图",
  zmls: "标配拉手", fmls: "背包拉手", st_val: "标准锁体",
  hysl: "3个/扇", sel_hys: "暗合页", qh: "", mshd: 80,
  sm: "", trim_style_outer: "", trim_style_inner: "", lock_side_offset: 150, ddh: "", sl: "1 樘", hhxd: "D",
  dhrq: new Date().toISOString().slice(0, 10).replace(/-/g, "."),
  door_type: "单门", mother_door_width: 600, mid_door_width: 400,
  has_pillar: false, pillar_width_str: "55/70",
  sel_kx: "右开", sel_nk: "内开",
  sel_qc: "无", qc_height: 400,
  has_mm: false, mm_height: 200,
  has_outer: true, trim_front_in: 160,
  has_inner: false, trim_back_in: 140,
  dw: 900, dh: 2100, overlap: 20,
  fw_left_str: "60/60", fw_right_str: "60/60", fw_top_str: "60/60",
  th_str: "55/70", threshold_type: "高低槛",
  left_gap: 2, right_gap: 2, top_gap: 5, bottom_gap: 7, middle_gap: 4,
  use_light_size: false, light_w: 0, light_h: 0,
  pdk: "60", sel_bz: "全包",
};
