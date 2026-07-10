"""
Pydantic 模型 - 请求/响应数据定义
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ===================== 表单数据模型（生成 CAD 用） =====================
class CADRequest(BaseModel):
    """生成 CAD 图纸的请求参数，对应 Streamlit 表单所有字段"""
    dhdw: str = ""                      # 订货单位/客户
    gdmc: str = ""                      # 项目名称
    ddh: str = ""                       # 订单号
    sl: str = "1 樘"                    # 数量
    hhxd: str = "D"                     # 制单人
    dhrq: str = ""                      # 交期日期 "YYYY.MM.DD"
    zzcl: str = "0.8的不锈钢镀铜"        # 制作材料
    ys: str = "2号色"                   # 颜色
    zmks: str = ""                      # 正面款式
    fmks: str = ""                      # 反面款式
    mshd: int = 80                      # 门扇厚度
    qh: str = ""                        # 墙厚
    sel_bz: str = "全包"                # 包装方式
    door_type: str = "单门"             # 门型
    sel_kx: str = "右开"                # 左右开向
    sel_nk: str = "内开"                # 内外开向
    use_light_size: bool = False        # 是否使用见光尺寸
    mark_light_size: bool = False       # 是否在洞口输入时标注见光尺寸
    dw: int = 900                       # 洞口总宽
    dh: int = 2100                      # 洞口总高
    light_w: int = 0                    # 见光宽
    light_h: int = 0                    # 见光高
    mother_door_width: int = 600        # 母门单扇宽
    mid_door_width: int = 400           # 中门单扇宽
    fw_left_str: str = "55/85"          # 左框宽 (小/大，按开向分配)
    fw_right_str: str = "55/62"         # 右框宽 (小/大，按开向分配)
    fw_top_str: str = "55/75"           # 上框宽 (小/大，按开向分配)
    threshold_type: str = "高低槛"      # 下槛方案
    th_str: str = "55/75"               # 下槛高度 (低/高)
    pdk: str = "60"                     # 平底槛厚度
    has_dj: bool = False                # 吊脚
    dj_height: int = 0                  # 吊脚高度
    zmls: str = "标配拉手"              # 正面拉手
    fmls: str = "标配拉手"              # 反面拉手
    handle_size: str = ""               # 拉手尺寸，如 40*800
    st_val: str = "连体锁"              # 锁体类型
    fingerprint_lock: str = ""          # 指纹锁
    sel_hys: str = ""                   # 合页样式
    hysl: str = "3个/扇"                # 合页数量
    has_outer: bool = True              # 外包套
    has_outer_portal: bool = False      # 外门头门柱（与外包套互斥）
    has_inner: bool = False             # 内包套
    overlap: int = 20                   # 压框
    overlap_front: int = 20             # 正面包套压框
    overlap_back: int = 20              # 反面包套压框
    trim_front_in: int = 160            # 外包套宽
    outer_portal_pillar_width: int = 160 # 外门柱宽度
    outer_portal_header_height: int = 220 # 外门头高度
    trim_back_in: int = 140             # 内包套宽
    sel_qc: str = "无"                  # 气窗
    qc_shape: str = "矩形气窗"          # 气窗形状
    is_arch_door: bool = False          # 圆弧门
    arch_spring_height: int = 1800      # 起弧高度
    is_integrated_door: bool = False    # 连体门
    integrated_panel_height: int = 300  # 连体门中间封板高度
    integrated_press_top_rail: int = 20 # 封板压框尺寸
    integrated_glass_bottom_rail: int = 20 # [兼容旧数据] 不再作为窗下框尺寸使用
    integrated_glass_height: int = 500  # 上方玻璃高度
    has_mm: bool = False                # 门楣
    has_pillar: bool = False            # 立柱
    qc_height: int = 400                # 气窗高
    mm_height: int = 200                # 门楣高
    pillar_width_str: str = "55/85"     # 立柱宽(小/大，按开向分配)
    sm: str = ""                        # 批注
    trim_style_outer: str = ""          # 外包套款式 斜包套/阶梯包套/工字形包套/01款包套/02款包套
    trim_style_inner: str = ""          # 内包套款式
    lock_side_offset: int = 0           # 兼容旧数据：旧锁边偏移量 (mm)
    door_panel_style: str = "无造型"     # 门板样式
    back_door_panel_style: str = "无造型"  # 反面门板样式
    child_door_panel_style: str = ""    # 子门/边扇门板样式，空=不单独绘制
    panel_lock_offset_x: int = 180      # 锁边向合页边偏移 X
    panel_hinge_offset_y: int = 100     # 合页边向锁边偏移 Y
    panel_middle_offset_z: int = 180    # B 区域上下向中间偏移 Z
    panel_plus_offset_a: int = 350      # H+ 第一段上偏移 A
    panel_plus_offset_b: int = 100      # H+ 第二段上偏移 B
    panel_three_col_a: int = 180        # 三列式 A 锁边区域宽，0 表示自动
    panel_three_col_b: int = 0          # 三列式 B 中间区域宽，0 表示自动
    panel_three_col_c: int = 100        # 三列式 C 合页区域宽，0 表示自动
    panel_disc_radius: int = 120        # 圆盘造型半径
    back_panel_lock_offset_x: int = 180
    back_panel_hinge_offset_y: int = 100
    back_panel_middle_offset_z: int = 180
    back_panel_plus_offset_a: int = 350
    back_panel_plus_offset_b: int = 100
    back_panel_three_col_a: int = 180
    back_panel_three_col_b: int = 0
    back_panel_three_col_c: int = 100
    back_panel_disc_radius: int = 120
    child_panel_lock_offset_x: int = 180
    child_panel_hinge_offset_y: int = 100
    child_panel_middle_offset_z: int = 180
    child_panel_plus_offset_a: int = 350
    child_panel_plus_offset_b: int = 100
    child_panel_three_col_a: int = 180
    child_panel_three_col_b: int = 0
    child_panel_three_col_c: int = 100
    child_panel_disc_radius: int = 120
    left_gap: int = 2                   # 左门缝
    right_gap: int = 2                  # 右门缝
    top_gap: int = 3                    # 上门缝
    bottom_gap: int = 5                 # 下门缝
    middle_gap: int = 2                 # 中缝
    left_right_gap_str: str = "0/0"     # [兼容旧数据] 左右间隙
    top_bottom_gap_str: str = "0/0"     # [兼容旧数据] 上下间隙


# ===================== 用户相关模型 =====================
class LoginRequest(BaseModel):
    uid: str
    pwd: str


class LoginResponse(BaseModel):
    success: bool
    message: str = ""
    user: Optional[Dict[str, Any]] = None
    token: Optional[str] = None


class UserCreateRequest(BaseModel):
    uid: str
    pwd: str
    role: str
    name: str


class ResetPasswordRequest(BaseModel):
    new_pwd: str


class UserDeleteRequest(BaseModel):
    uid: str


# ===================== 任务相关模型 =====================
class TaskCreateRequest(BaseModel):
    """创建新任务的请求"""
    params: Dict[str, Any]              # 表单数据（即 get_current_form_data 的结果）
    ref_text: str = ""                  # 沟通要求文字
    ref_images: List[str] = []          # 参考图片 base64 数组


class ChangeEntry(BaseModel):
    """单个字段变更记录"""
    field: str
    old: str = ""
    new: str = ""


class HistoryEntry(BaseModel):
    """单次修改记录"""
    modified_by: str
    modified_at: str
    changes: List[ChangeEntry] = []


class TaskUpdateRequest(BaseModel):
    """更新任务的请求"""
    status: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    drawing_img_b64: Optional[str] = None
    review_feedback: Optional[str] = None
    ref_text: Optional[str] = None
    ref_images: Optional[List[str]] = None


class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    date: str
    status: str
    customer: str
    project: str
    door_type: str
    size: str
    params: Dict[str, Any]
    ref_text: str = ""
    ref_images: List[str] = []
    drawing_img_b64: Optional[str] = None
    review_feedback: str = ""
    history: List[HistoryEntry] = []


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
