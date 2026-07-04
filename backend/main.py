"""
西州将军铜门 - 生产图纸协同系统 FastAPI 后端
从 door_26.py (Streamlit 单体应用) 提取核心逻辑重构为前后端分离架构
"""
import io
import json
import os
import uuid
import datetime
from typing import List, Optional, Dict
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import DATA_DIR, JWT_SECRET
from database import UserDatabaseManager, TaskDatabaseManager, hash_password
from auth import (
    ENTRY_ROLES,
    TASK_ROLES,
    create_token,
    get_current_user,
    public_user_info,
    public_users_map,
    require_roles,
    require_super_admin,
    verify_token,
)
from models import (
    CADRequest,
    LoginRequest, LoginResponse,
    UserCreateRequest, ResetPasswordRequest,
    TaskCreateRequest, TaskUpdateRequest, TaskResponse, TaskListResponse,
)
from drawing import run_integrated_system
from drawing import _load_template
from cad_preview import render_dxf_svg
from utils import parse_dim_str, parse_gap_str
from quote_routes import quote_router
from render_routes import render_router

# ===================== FastAPI 应用初始化 =====================
app = FastAPI(
    title="西州将军铜门 - 生产图纸协同系统 API",
    version="1.0.0",
    description="铜门生产图纸协同系统后端服务，提供 CAD 图纸生成和任务流转管理",
)

_cors_origins_str = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://124.223.87.161:3000")
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(quote_router)
app.include_router(render_router)

# ===================== 数据库实例 =====================
user_db = UserDatabaseManager()
task_db = TaskDatabaseManager()

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)


# ===================== 启动事件：预加载模板 =====================
@app.on_event("startup")
async def startup_preload_template():
    """应用启动时预加载 DXF 模板到内存缓存"""
    _load_template()
    print(f"[startup] DXF 模板已加载到内存缓存")


# ===================== 辅助函数：表单参数组装 =====================
def build_cad_params(req: CADRequest):
    """
    将 CADRequest 组装为 info_map, check_map, draw_params
    原封不动地从 door_26.py 的 generate_cad_trigger 逻辑提取
    """
    # --- 包套批注 ---
    def _format_handle_size(value: str):
        normalized = (value or "").lower().replace("×", "*").replace("x", "*")
        parts = [part.strip() for part in normalized.split("*") if part.strip()]
        if len(parts) != 2:
            return value.strip(), None
        try:
            a = float(parts[0])
            b = float(parts[1])
        except ValueError:
            return value.strip(), None
        width, height = min(a, b), max(a, b)
        def fmt(num: float):
            return str(int(num)) if num.is_integer() else str(num)
        return f"{fmt(width)}mm*{fmt(height)}mm", (width, height)

    overlap_front = req.overlap_front if req.overlap_front is not None else req.overlap
    overlap_back = req.overlap_back if req.overlap_back is not None else req.overlap
    current_note = req.sm
    frame_notes = []

    if req.has_outer:
        outer_w = req.trim_front_in
        frame_notes.append(f"外门套宽/压墙/压框={outer_w}/{outer_w - overlap_front}/{overlap_front}mm")
    elif req.has_outer_portal:
        pillar_w = req.outer_portal_pillar_width
        header_h = req.outer_portal_header_height
        frame_notes.append(f"外门头门柱：门柱宽/门头高/压框={pillar_w}/{header_h}/{overlap_front}mm")

    if req.has_inner:
        inner_w = req.trim_back_in
        frame_notes.append(f"内门套宽/压墙/压框={inner_w}/{inner_w - overlap_back}/{overlap_back}mm")

    if req.handle_size.strip():
        handle_label, _handle_pair = _format_handle_size(req.handle_size)
        if req.zmls == "自制长拉手":
            frame_notes.append(f"自制长拉手尺寸为：{handle_label}")
        else:
            frame_notes.append(f"拉手尺寸={handle_label}")

    if frame_notes:
        note_line = "\n".join(frame_notes)
        if note_line not in current_note:
            if current_note.strip():
                final_note = current_note + "\n" + note_line
            else:
                final_note = note_line
        else:
            final_note = current_note
    else:
        final_note = current_note
    door_type = "四开门" if req.door_type == "折叠四开门" else req.door_type

    # --- 框宽解析 ---
    fw_left_str = req.fw_left_str
    fw_right_str = req.fw_right_str
    if door_type in ("对开门", "子母门", "两定两开", "四开门") and fw_left_str == "55/85" and fw_right_str == "55/62":
        fw_left_str = "55/62"
        fw_right_str = "55/62"

    parts_left = parse_dim_str(fw_left_str, 60, 60)
    left_small, left_big = min(parts_left[0], parts_left[1]), max(parts_left[0], parts_left[1])

    parts_right = parse_dim_str(fw_right_str, 60, 60)
    right_small, right_big = min(parts_right[0], parts_right[1]), max(parts_right[0], parts_right[1])

    parts_top = parse_dim_str(req.fw_top_str, 60, 60)
    fw_top_small, fw_top_big = min(parts_top[0], parts_top[1]), max(parts_top[0], parts_top[1])

    parts_th = parse_dim_str(req.th_str, 60, 60)
    th_small, th_big = min(parts_th[0], parts_th[1]), max(parts_th[0], parts_th[1])

    # --- 框宽按开向分配：输入值只表示小/大，不再表示外/内 ---
    if req.sel_nk == "内开":
        # 内开时外侧（正面）用大值，内侧（背面）用小值。
        lwf, rwf = left_big, right_big
        lwb, rwb = left_small, right_small
        ftf, ftb = fw_top_big, fw_top_small
        thf, thb = th_big, th_small
    else:
        # 外开时内侧（背面）用大值，外侧（正面）用小值。
        lwf, rwf = left_small, right_small
        lwb, rwb = left_big, right_big
        ftf, ftb = fw_top_small, fw_top_big
        thf, thb = th_small, th_big

    dw = req.dw
    dh = req.dh

    # --- 见光尺寸反算 ---
    if req.use_light_size:
        lw = req.light_w
        lh = req.light_h
        if lw > 0 and lh > 0:
            from drawing import DimensionCalculator
            calc_p = {
                "dw": dw, "dh": dh,
                "left_width_front": lwf, "right_width_front": rwf,
                "left_width_back": lwb, "right_width_back": rwb,
                "fw_top_front": ftf, "fw_top_back": ftb,
                "th_front": thf, "th_back": thb,
                "nk": req.sel_nk
            }
            calc = DimensionCalculator(calc_p)
            res_light = calc.calculate_from_light_size(lw, lh, req.sel_nk == "外开")
            dw, dh = res_light[0], res_light[1]

    is_hanging_threshold = req.threshold_type == "吊脚" or req.has_dj

    if is_hanging_threshold:
        thf = 0
        thb = 0

    # --- 下槛处理 ---
    dj_val = ""
    djg_val = ""
    if is_hanging_threshold:
        dxk_val = ""
        gxk_val = ""
        pdk_val = ""
        dj_val = "√"
        djg_val = str(req.dj_height or "")
    elif req.threshold_type == "平底槛":
        dxk_val = ""
        gxk_val = ""
        pdk_val = req.pdk
    else:
        parts = req.th_str.split("/")
        if len(parts) > 1:
            dxk_val = parts[0]
            gxk_val = parts[-1]
        else:
            dxk_val = parts[0]
            gxk_val = parts[0]
        pdk_val = ""

    # --- 门型中文名 ---
    if door_type == "两定两开":
        dt_cn = "两定两开门"
    else:
        dt_cn = door_type

    qh_val = ""
    if req.qh:
        qh_val = f"{req.qh} mm"

    mshd_val = f"{req.mshd} mm"

    qc_height_val = 0
    if req.sel_qc != "无":
        qc_height_val = req.qc_height

    mm_height_val = 0
    if req.has_mm:
        mm_height_val = req.mm_height

    # --- info_map ---
    info_map = {
        "DHDW": req.dhdw, "GDMC": req.gdmc, "ZZCL": req.zzcl,
        "DHRQ": req.dhrq, "DDH": req.ddh, "SL": req.sl,
        "YS": req.ys, "ZMLS": req.zmls, "FMLS": req.fmls,
        "ST": req.st_val, "ZWS": req.fingerprint_lock, "HYSL": req.hysl, "QH": qh_val,
        "MSHD": mshd_val, "HHXD": req.hhxd, "BZ": final_note,
        "DOOR_TYPE": door_type, "MOTHER_DOOR_WIDTH": req.mother_door_width,
        "MID_DOOR_WIDTH": req.mid_door_width, "PILLAR_WIDTH_STR": req.pillar_width_str,
        "HAS_PILLAR": req.has_pillar, "HYYS": req.sel_hys,
        "DXK": dxk_val, "GXK": gxk_val, "PXK": pdk_val, "DJ": dj_val, "DJG": djg_val, "MX": dt_cn,
        "QC_HEIGHT": qc_height_val, "HAS_MM": req.has_mm, "MM_HEIGHT": mm_height_val,
        "QC_SHAPE": req.qc_shape,
        "IS_INTEGRATED_DOOR": req.is_integrated_door,
        "INTEGRATED_PANEL_HEIGHT": req.integrated_panel_height,
        "INTEGRATED_PRESS_TOP_RAIL": req.integrated_press_top_rail,
        "INTEGRATED_GLASS_BOTTOM_RAIL": req.integrated_glass_bottom_rail,
        "INTEGRATED_GLASS_HEIGHT": req.integrated_glass_height,
        "ZMKS": req.zmks, "FMKS": req.fmks,
        "TRIM_STYLE_OUTER": req.trim_style_outer,
        "TRIM_STYLE_INNER": req.trim_style_inner,
        "DOOR_PANEL_STYLE": req.door_panel_style,
        "BACK_DOOR_PANEL_STYLE": req.back_door_panel_style,
        "CHILD_DOOR_PANEL_STYLE": req.child_door_panel_style,
        "PANEL_LOCK_OFFSET_X": req.panel_lock_offset_x,
        "PANEL_HINGE_OFFSET_Y": req.panel_hinge_offset_y,
        "PANEL_MIDDLE_OFFSET_Z": req.panel_middle_offset_z,
        "PANEL_PLUS_OFFSET_A": req.panel_plus_offset_a,
        "PANEL_PLUS_OFFSET_B": req.panel_plus_offset_b,
        "PANEL_THREE_COL_A": req.panel_three_col_a,
        "PANEL_THREE_COL_B": req.panel_three_col_b,
        "PANEL_THREE_COL_C": req.panel_three_col_c,
        "PANEL_DISC_RADIUS": req.panel_disc_radius,
        "BACK_PANEL_LOCK_OFFSET_X": req.back_panel_lock_offset_x,
        "BACK_PANEL_HINGE_OFFSET_Y": req.back_panel_hinge_offset_y,
        "BACK_PANEL_MIDDLE_OFFSET_Z": req.back_panel_middle_offset_z,
        "BACK_PANEL_PLUS_OFFSET_A": req.back_panel_plus_offset_a,
        "BACK_PANEL_PLUS_OFFSET_B": req.back_panel_plus_offset_b,
        "BACK_PANEL_THREE_COL_A": req.back_panel_three_col_a,
        "BACK_PANEL_THREE_COL_B": req.back_panel_three_col_b,
        "BACK_PANEL_THREE_COL_C": req.back_panel_three_col_c,
        "BACK_PANEL_DISC_RADIUS": req.back_panel_disc_radius,
        "CHILD_PANEL_LOCK_OFFSET_X": req.child_panel_lock_offset_x,
        "CHILD_PANEL_HINGE_OFFSET_Y": req.child_panel_hinge_offset_y,
        "CHILD_PANEL_MIDDLE_OFFSET_Z": req.child_panel_middle_offset_z,
        "CHILD_PANEL_PLUS_OFFSET_A": req.child_panel_plus_offset_a,
        "CHILD_PANEL_PLUS_OFFSET_B": req.child_panel_plus_offset_b,
        "CHILD_PANEL_THREE_COL_A": req.child_panel_three_col_a,
        "CHILD_PANEL_THREE_COL_B": req.child_panel_three_col_b,
        "CHILD_PANEL_THREE_COL_C": req.child_panel_three_col_c,
        "CHILD_PANEL_DISC_RADIUS": req.child_panel_disc_radius,
        "HANDLE_SIZE": req.handle_size,
        "FINGERPRINT_LOCK": req.fingerprint_lock,
    }

    # --- check_map ---
    out_mark = "√" if req.has_outer else ""
    outer_portal_mark = "√" if req.has_outer_portal else ""
    in_mark = "√" if req.has_inner else ""
    nk_mark = "√" if req.sel_nk == "内开" else ""
    wk_mark = "√" if req.sel_nk == "外开" else ""
    kxr_mark = "√" if req.sel_kx == "右开" else ""
    kxl_mark = "√" if req.sel_kx == "左开" else ""

    lz_y, lz_n = ("√", "") if req.has_pillar else ("", "√")
    mm_y, mm_n = ("√", "") if req.has_mm else ("", "√")

    qc_g = "√" if req.sel_qc == "玻璃" else ""
    qc_s = "√" if req.sel_qc == "封闭" else ""

    bz_q = "√" if req.sel_bz == "全包" else ""
    bz_m = "√" if req.sel_bz == "木箱" else ""

    gdk_m = "√" if req.threshold_type == "高低槛" else ""
    pdk_m = "√" if req.threshold_type == "平底槛" else ""
    dj_m = "√" if req.threshold_type == "吊脚" or req.has_dj else ""

    check_map = {
        "kx": req.sel_kx, "nk": req.sel_nk, "qc": req.sel_qc,
        "lz": "有" if req.has_pillar else "无",
        "bz": req.sel_bz, "hys": req.sel_hys,
        "mm": "有" if req.has_mm else "无",
        "OUTER": out_mark, "INNER": in_mark,
        "OUTER_PORTAL": outer_portal_mark,
        "NK": nk_mark, "WK": wk_mark,
        "KX_RIGHT": kxr_mark, "KX_LEFT": kxl_mark,
        "LZ_YES": lz_y, "LZ_NO": lz_n,
        "MM_YES": mm_y, "MM_NO": mm_n,
        "QC_GLASS": qc_g, "QC_SEAL": qc_s,
        "BZ_QB": bz_q, "BZ_MX": bz_m,
        "GDK": gdk_m, "PDK": pdk_m, "DJ": dj_m,
        "threshold": req.threshold_type,
    }

    # --- draw_params ---
    trim_f = req.trim_front_in if req.has_outer else (req.outer_portal_pillar_width if req.has_outer_portal else 0)
    trim_f_top = req.trim_front_in if req.has_outer else (req.outer_portal_header_height if req.has_outer_portal else 0)
    trim_b = req.trim_back_in if req.has_inner else 0

    draw_params = {
        "dw": dw, "dh": dh,
        "left_width_front": lwf, "right_width_front": rwf,
        "left_width_back": lwb, "right_width_back": rwb,
        "fw_top_front": ftf, "fw_top_back": ftb,
        "th_front": thf, "th_back": thb,
        "has_dj": is_hanging_threshold,
        "dj_height": req.dj_height,
        "trim_front": trim_f, "trim_front_top": trim_f_top, "trim_back": trim_b, "trim_back_top": trim_b,
        "has_outer_portal": req.has_outer_portal,
        "overlap": req.overlap,
        "overlap_front": overlap_front,
        "overlap_back": overlap_back,
        "door_type": door_type,
        "mother_door_width": req.mother_door_width,
        "mid_door_width": req.mid_door_width,
        "pillar_width_str": req.pillar_width_str,
        "has_pillar": req.has_pillar,
        "kx": req.sel_kx, "nk": req.sel_nk,
        "qc": req.sel_qc, "qc_height": qc_height_val, "qc_shape": req.qc_shape,
        "is_integrated_door": req.is_integrated_door,
        "integrated_panel_height": req.integrated_panel_height,
        "integrated_press_top_rail": req.integrated_press_top_rail,
        "integrated_glass_bottom_rail": req.integrated_glass_bottom_rail,
        "integrated_glass_height": req.integrated_glass_height,
        "has_mm": req.has_mm, "mm_height": mm_height_val,
        "hys": req.sel_hys, "hysl": req.hysl,
        # 间隙：优先使用新独立字段，回退到旧字符串格式
        "left_right_gap": (req.left_gap, req.right_gap) if (req.left_gap or req.right_gap) else parse_gap_str(req.left_right_gap_str, 0),
        "top_bottom_gap": (req.top_gap, req.bottom_gap) if (req.top_gap or req.bottom_gap) else parse_gap_str(req.top_bottom_gap_str, 0),
        "middle_gap": req.middle_gap,
        "use_light_size": req.use_light_size,
        "mark_light_size": req.mark_light_size,
        "light_w": req.light_w, "light_h": req.light_h,
        "zmls": req.zmls, "fmls": req.fmls,
        "trim_style_outer": req.trim_style_outer,
        "trim_style_inner": req.trim_style_inner,
        "door_panel_style": req.door_panel_style,
        "back_door_panel_style": req.back_door_panel_style,
        "child_door_panel_style": req.child_door_panel_style,
        "panel_lock_offset_x": req.panel_lock_offset_x,
        "panel_hinge_offset_y": req.panel_hinge_offset_y,
        "panel_middle_offset_z": req.panel_middle_offset_z,
        "panel_plus_offset_a": req.panel_plus_offset_a,
        "panel_plus_offset_b": req.panel_plus_offset_b,
        "panel_three_col_a": req.panel_three_col_a,
        "panel_three_col_b": req.panel_three_col_b,
        "panel_three_col_c": req.panel_three_col_c,
        "panel_disc_radius": req.panel_disc_radius,
        "back_panel_lock_offset_x": req.back_panel_lock_offset_x,
        "back_panel_hinge_offset_y": req.back_panel_hinge_offset_y,
        "back_panel_middle_offset_z": req.back_panel_middle_offset_z,
        "back_panel_plus_offset_a": req.back_panel_plus_offset_a,
        "back_panel_plus_offset_b": req.back_panel_plus_offset_b,
        "back_panel_three_col_a": req.back_panel_three_col_a,
        "back_panel_three_col_b": req.back_panel_three_col_b,
        "back_panel_three_col_c": req.back_panel_three_col_c,
        "back_panel_disc_radius": req.back_panel_disc_radius,
        "child_panel_lock_offset_x": req.child_panel_lock_offset_x,
        "child_panel_hinge_offset_y": req.child_panel_hinge_offset_y,
        "child_panel_middle_offset_z": req.child_panel_middle_offset_z,
        "child_panel_plus_offset_a": req.child_panel_plus_offset_a,
        "child_panel_plus_offset_b": req.child_panel_plus_offset_b,
        "child_panel_three_col_a": req.child_panel_three_col_a,
        "child_panel_three_col_b": req.child_panel_three_col_b,
        "child_panel_three_col_c": req.child_panel_three_col_c,
        "child_panel_disc_radius": req.child_panel_disc_radius,
        "handle_size": req.handle_size,
        "fingerprint_lock": req.fingerprint_lock,
    }

    return info_map, check_map, draw_params


# ===================== API: CAD 图纸生成 =====================
@app.post("/api/generate_cad")
def generate_cad(req: CADRequest, current_user: Dict = Depends(get_current_user)):
    """
    接收表单数据，调用 ezdxf 读取 template.dxf 生成图纸，
    并以 .dxf 文件流形式返回。
    """
    info_map, check_map, draw_params = build_cad_params(req)

    progress_msgs = []
    def progress_callback(msg: str):
        progress_msgs.append(msg)

    result_msg, buffer = run_integrated_system(info_map, check_map, draw_params, progress_callback)

    if buffer is None:
        raise HTTPException(status_code=500, detail=result_msg)

    # ezdxf 写入 StringIO，转换为 bytes 用于 HTTP 响应
    dxf_bytes = buffer.getvalue().encode('utf-8')
    bytes_io = io.BytesIO(dxf_bytes)

    # 文件名 URL 编码（RFC 5987），避免中文导致的 latin-1 编码错误
    ts = datetime.datetime.now().strftime("%Y%m%d")
    safe_customer = "".join(
        ch for ch in (req.dhdw or "未命名").strip()
        if ch not in '\\/:*?"<>|' and not ch.isspace()
    ) or "未命名"
    raw_filename = f"{safe_customer}{ts}.dxf"
    encoded_filename = quote(raw_filename)
    ascii_filename = "drawing.dxf"

    return StreamingResponse(
        bytes_io,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_filename}"; '
                f"filename*=UTF-8''{encoded_filename}"
            )
        }
    )


# ===================== API: 用户登录 =====================
@app.post("/api/generate_cad_preview")
def generate_cad_preview(req: CADRequest, current_user: Dict = Depends(get_current_user)):
    """
    Reuse the CAD export path and render the generated DXF as an SVG preview.
    """
    info_map, check_map, draw_params = build_cad_params(req)

    progress_msgs = []

    def progress_callback(msg: str):
        progress_msgs.append(msg)

    result_msg, buffer = run_integrated_system(info_map, check_map, draw_params, progress_callback)

    if buffer is None:
        raise HTTPException(status_code=500, detail=result_msg)

    try:
        svg = render_dxf_svg(buffer.getvalue())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CAD preview failed: {exc}") from exc

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user_info = user_db.authenticate(req.uid, req.pwd)
    if user_info:
        token = create_token(user_info["uid"])
        return LoginResponse(
            success=True,
            message="登录成功",
            user=public_user_info(user_info),
            token=token,
        )
    else:
        return LoginResponse(success=False, message="账号或密码错误！")


# ===================== API: 用户管理 =====================
@app.get("/api/users")
def list_users(current_user: Dict = Depends(require_super_admin)):
    """获取所有用户列表"""
    users = user_db.load_all_users()
    return {"users": public_users_map(users), "total": len(users)}


@app.post("/api/users")
def create_user(req: UserCreateRequest, current_user: Dict = Depends(require_super_admin)):
    """创建或更新用户"""
    if not req.uid or not req.name or not req.pwd:
        raise HTTPException(status_code=400, detail="请填写完整账号信息。")
    if req.uid == "admin":
        raise HTTPException(status_code=400, detail="内置 admin 账号不能通过普通创建接口覆盖")
    user_db.add_or_update_user(req.uid, req.pwd, req.role, req.name)
    return {"success": True, "message": f"成功保存账号: {req.uid}"}


@app.delete("/api/users/{uid}")
def delete_user(uid: str, current_user: Dict = Depends(require_super_admin)):
    """删除用户（admin 不可删）"""
    if uid == "admin":
        raise HTTPException(status_code=400, detail="系统内置管理员不可删除")
    user_db.delete_user(uid)
    return {"success": True, "message": f"已删除账号: {uid}"}


@app.put("/api/users/{uid}/reset-password")
def reset_password(uid: str, req: ResetPasswordRequest, current_user: Dict = Depends(require_super_admin)):
    """重置用户密码"""
    users = user_db.load_all_users()
    if uid not in users:
        raise HTTPException(status_code=404, detail="用户不存在")
    users[uid]["password"] = hash_password(req.new_pwd)
    user_db.save(users)
    return {"success": True, "message": f"已重置 {uid} 的密码"}


# ===================== API: 任务管理 =====================
@app.get("/api/tasks", response_model=TaskListResponse)
def list_tasks(date: Optional[str] = Query(None, description="按日期筛选 YYYY.MM.DD"),
               status: Optional[str] = Query(None, description="按状态筛选"),
               limit: int = Query(50, ge=1, le=200, description="每页条数"),
               offset: int = Query(0, ge=0, description="偏移量"),
               current_user: Dict = Depends(get_current_user)):
    """获取任务列表，支持按日期/状态筛选 + 分页（不返回 Base64 图片数据以优化性能）"""
    all_tasks = task_db.load_all_tasks()
    filtered = []
    status_set = set(s.strip() for s in status.split(",")) if status else None
    for t in all_tasks:
        if date and t.get("date") != date:
            continue
        if status_set and t.get("status") not in status_set:
            continue
        t = dict(t)
        t.pop("ref_img_b64", None)
        t.pop("drawing_img_b64", None)
        filtered.append(t)
    total = len(filtered)
    page = filtered[offset:offset + limit]
    return TaskListResponse(tasks=page, total=total)


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, current_user: Dict = Depends(get_current_user)):
    """获取单个任务详情"""
    task = task_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.post("/api/tasks", response_model=TaskResponse)
def create_task(req: TaskCreateRequest, current_user: Dict = Depends(require_roles(*ENTRY_ROLES))):
    """创建新任务（录入员提交订单）"""
    task_id = str(uuid.uuid4())[:8]
    new_task = {
        "id": task_id,
        "date": req.params.get("dhrq", datetime.date.today().strftime("%Y.%m.%d")),
        "status": "待绘制",
        "customer": req.params.get("dhdw", ""),
        "project": req.params.get("gdmc", ""),
        "door_type": req.params.get("door_type", ""),
        "size": f"{req.params.get('dw', 0)} x {req.params.get('dh', 0)} (洞口)",
        "params": req.params,
        "ref_text": req.ref_text,
        "ref_images": req.ref_images,
        "drawing_img_b64": None,
        "review_feedback": "",
        "history": [],
    }
    try:
        task_db.add_task(new_task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 返回完整任务（包含已还原的图片）
    return task_db.get_task(task_id)


def _build_history(old_params: Dict, new_params: Dict, user_name: str) -> Dict:
    """对比新旧params，生成单条修改记录"""
    changes = []
    for key in set(list(old_params.keys()) + list(new_params.keys())):
        old_val = old_params.get(key, "")
        new_val = new_params.get(key, "")
        if str(old_val) != str(new_val):
            changes.append({"field": key, "old": str(old_val), "new": str(new_val)})
    return {
        "modified_by": user_name,
        "modified_at": datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S"),
        "changes": changes,
    }


@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, req: TaskUpdateRequest, current_user: Dict = Depends(require_roles(*TASK_ROLES))):
    """更新任务（状态流转、上传图纸、提交审核意见等）"""
    existing = task_db.get_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="任务不存在")

    update_data = {}
    if req.status is not None:
        update_data["status"] = req.status
    if req.params is not None:
        update_data["params"] = req.params
        # 生成修改记录
        old_params = existing.get("params", {})
        history_entry = _build_history(old_params, req.params, current_user.get("name", current_user.get("uid", "")))
        if history_entry["changes"]:
            old_history = existing.get("history", [])
            update_data["history"] = old_history + [history_entry]
    if req.drawing_img_b64 is not None:
        update_data["drawing_img_b64"] = req.drawing_img_b64
    if req.review_feedback is not None:
        update_data["review_feedback"] = req.review_feedback
    if req.ref_text is not None:
        update_data["ref_text"] = req.ref_text
    if req.ref_images is not None:
        update_data["ref_images"] = req.ref_images

    try:
        task_db.update_task(task_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return task_db.get_task(task_id)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, current_user: Dict = Depends(require_super_admin)):
    """删除任务"""
    existing = task_db.get_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        task_db.delete_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "message": f"已删除任务: {task_id}"}


# ===================== 后台管理 =====================
@app.get("/api/admin/tasks")
def admin_list_all_tasks(current_user: Dict = Depends(require_super_admin)):
    """管理员上帝视角：返回全部订单数据（纯文本，不含 Base64 图片）"""
    all_tasks = task_db.load_all_tasks()
    stripped = []
    for t in all_tasks:
        t = dict(t)
        t.pop("ref_img_b64", None)
        t.pop("drawing_img_b64", None)
        stripped.append(t)
    return {"tasks": stripped, "total": len(stripped)}


# ===================== 认证相关 =====================
@app.get("/api/auth/verify")
def auth_verify(current_user: dict = Depends(get_current_user)):
    """验证 token 有效性，返回当前用户信息"""
    # 不返回密码哈希
    return {
        "uid": current_user["uid"],
        "role": current_user["role"],
        "name": current_user["name"],
        "default_module": current_user["default_module"],
    }


# ===================== 下拉选项管理 =====================
import threading as _threading

_DROPDOWN_OPTIONS_PATH = os.path.join(DATA_DIR, "dropdown_options.json")
_dropdown_lock = _threading.Lock()
_DEFAULT_DROPDOWN_OPTIONS = {
    "DOOR_TYPES": ["单门", "对开门", "子母门", "两定两开", "四开门"],
    "KX_OPTIONS": ["左开", "右开"],
    "NK_OPTIONS": ["内开", "外开"],
    "MATERIALS": ["0.8的不锈钢镀铜", "1.0的不锈钢镀铜", "1.2的不锈钢镀铜", "0.8的纯铜", "1.0的纯铜", "1.2的纯铜", "纯铝"],
    "HANDLES": ["标配拉手", "A1022", "A635", "分体拉手", "铝雕拉手", "铝雕滑盖拉手", "铝雕长拉手", "自制长拉手", "背包拉手"],
    "LOCKS": ["连体锁", "标准锁体", "防盗锁体", "霸王锁体", "快装锁体"],
    "FINGERPRINT_LOCKS": ["", "无", "安志杰AF-12", "Q3指纹锁", "T5指纹锁", "客备指纹锁"],
    "HINGES": ["葫芦头合页", "可拆卸合页", "三维可调合页", "暗合页", "北京暗合页", "明合页暗装", "明合页"],
    "TRIM_STYLES": ["平包套", "斜包套", "阶梯包套", "工字形包套", "01款包套", "02款包套", "03款包套"],
    "COLOR_PRESETS": ["2号色", "2.3号色", "2.5号色", "3号色", "6号色乱纹", "7号色乱纹"],
    "THRESHOLD_OPTIONS": ["高低槛", "平底槛", "吊脚"],
    "QC_OPTIONS": ["无", "玻璃", "封闭"],
    "BZ_OPTIONS": ["全包", "木箱"],
    "HYSL_OPTIONS": ["3个/扇", "2个/扇", "4个/扇", "5个/扇"],
}
_DROPDOWN_ALIASES = {
    "三位可调合页": "三维可调合页",
    "折叠四开门": "四开门",
}

_EMPTY_ALLOWED_DROPDOWNS = {"FINGERPRINT_LOCKS"}

def _normalize_dropdown_value(key: str, value) -> str:
    raw_text = str(value).strip()
    if key == "FINGERPRINT_LOCKS":
        if raw_text == "":
            return ""
        if raw_text == "客备":
            return "客备指纹锁"
    return _DROPDOWN_ALIASES.get(raw_text, raw_text).strip()

def _load_dropdown_options() -> dict:
    try:
        with open(_DROPDOWN_OPTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_dropdown_options(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with _dropdown_lock:
        with open(_DROPDOWN_OPTIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _merge_dropdown_options(configured: dict) -> dict:
    merged = {}
    all_keys = list(_DEFAULT_DROPDOWN_OPTIONS.keys())
    for key in configured:
        if key not in all_keys:
            all_keys.append(key)

    for key in all_keys:
        values = []
        for value in _DEFAULT_DROPDOWN_OPTIONS.get(key, []) + configured.get(key, []):
            text = _normalize_dropdown_value(key, value)
            if (text or key in _EMPTY_ALLOWED_DROPDOWNS) and text not in values:
                values.append(text)
        merged[key] = values
    return merged


@app.get("/api/admin/dropdown-options")
def get_dropdown_options(current_user: dict = Depends(get_current_user)):
    """获取所有下拉选项配置"""
    return {"options": _merge_dropdown_options(_load_dropdown_options())}


@app.put("/api/admin/dropdown-options")
def update_dropdown_options(data: dict, current_user: dict = Depends(require_super_admin)):
    """更新某个下拉选项列表（data: {KEY: [...]}）"""
    current = _load_dropdown_options()
    for key, values in data.items():
        if isinstance(values, list):
            current[key] = [_normalize_dropdown_value(key, v) for v in values]
    _save_dropdown_options(current)
    return {"options": _merge_dropdown_options(current)}


# ===================== 健康检查 =====================
@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "西州将军铜门 - 协同平台 API"}


# ===================== 启动入口 =====================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
