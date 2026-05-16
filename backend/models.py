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
    zmks: str = "按图"                  # 正面款式
    fmks: str = "按图"                  # 反面款式
    mshd: int = 80                      # 门扇厚度
    qh: str = ""                        # 墙厚
    sel_bz: str = "全包"                # 包装方式
    door_type: str = "单门"             # 门型
    sel_kx: str = "右开"                # 左右开向
    sel_nk: str = "内开"                # 内外开向
    use_light_size: bool = False        # 是否使用见光尺寸
    dw: int = 900                       # 洞口总宽
    dh: int = 2100                      # 洞口总高
    light_w: int = 0                    # 见光宽
    light_h: int = 0                    # 见光高
    mother_door_width: int = 600        # 母门单扇宽
    mid_door_width: int = 400           # 中门单扇宽
    fw_left_str: str = "60/60"          # 左框宽 (外/内)
    fw_right_str: str = "60/60"         # 右框宽 (外/内)
    fw_top_str: str = "60/60"           # 上框宽 (外/内)
    threshold_type: str = "高低槛"      # 下槛方案
    th_str: str = "55/70"               # 下槛高度 (低/高)
    pdk: str = "60"                     # 平底槛厚度
    zmls: str = "标配拉手"              # 正面拉手
    fmls: str = "背包拉手"              # 反面拉手
    st_val: str = "标准锁体"            # 锁体类型
    sel_hys: str = "暗合页"             # 合页样式
    hysl: str = "3个/扇"                # 合页数量
    has_outer: bool = True              # 外包套
    has_inner: bool = False             # 内包套
    overlap: int = 20                   # 压框
    trim_front_in: int = 160            # 外包套宽
    trim_back_in: int = 140             # 内包套宽
    sel_qc: str = "无"                  # 气窗
    has_mm: bool = False                # 门楣
    has_pillar: bool = False            # 立柱
    qc_height: int = 400                # 气窗高
    mm_height: int = 200                # 门楣高
    pillar_width_str: str = "55/70"     # 立柱宽(外/内)
    sm: str = ""                        # 批注
    trim_style_outer: str = ""          # 外包套款式 斜包套/阶梯包套/工字形包套/01款包套/02款包套
    trim_style_inner: str = ""          # 内包套款式
    lock_side_offset: int = 150         # 锁边偏移量 (mm)
    left_gap: int = 2                   # 左门缝
    right_gap: int = 2                  # 右门缝
    top_gap: int = 5                    # 上门缝
    bottom_gap: int = 7                 # 下门缝
    middle_gap: int = 4                 # 中缝
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
    ref_img_b64: Optional[str] = None   # 参考图片 base64


class TaskUpdateRequest(BaseModel):
    """更新任务的请求"""
    status: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    drawing_img_b64: Optional[str] = None
    review_feedback: Optional[str] = None


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
    ref_img_b64: Optional[str] = None
    drawing_img_b64: Optional[str] = None
    review_feedback: str = ""


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
