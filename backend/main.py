"""
西州将军铜门 - 生产图纸协同系统 FastAPI 后端
从 door_26.py (Streamlit 单体应用) 提取核心逻辑重构为前后端分离架构
"""
import io
import os
import uuid
import datetime
from typing import List, Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import DATA_DIR, JWT_SECRET
from database import UserDatabaseManager, TaskDatabaseManager, hash_password
from auth import create_token, verify_token, get_current_user
from models import (
    CADRequest,
    LoginRequest, LoginResponse,
    UserCreateRequest, ResetPasswordRequest,
    TaskCreateRequest, TaskUpdateRequest, TaskResponse, TaskListResponse,
)
from drawing import run_integrated_system
from utils import parse_dim_str, parse_gap_str

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

# ===================== 数据库实例 =====================
user_db = UserDatabaseManager()
task_db = TaskDatabaseManager()

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)


# ===================== 辅助函数：表单参数组装 =====================
def build_cad_params(req: CADRequest):
    """
    将 CADRequest 组装为 info_map, check_map, draw_params
    原封不动地从 door_26.py 的 generate_cad_trigger 逻辑提取
    """
    # --- 包套批注 ---
    outer_width = req.trim_front_in if req.has_outer else 0
    overlap = req.overlap
    note_line = f"门套宽/压墙/压框={outer_width}/{outer_width - overlap}/{overlap}mm"
    current_note = req.sm
    if note_line not in current_note:
        if current_note.strip():
            final_note = current_note + "\n" + note_line
        else:
            final_note = note_line
    else:
        final_note = current_note

    # --- 框宽解析 ---
    parts_left = parse_dim_str(req.fw_left_str, 60, 60)
    left_out, left_in = parts_left[0], parts_left[1]

    parts_right = parse_dim_str(req.fw_right_str, 60, 60)
    right_out, right_in = parts_right[0], parts_right[1]

    parts_top = parse_dim_str(req.fw_top_str, 60, 60)
    fw_top_out, fw_top_in = parts_top[0], parts_top[1]

    parts_th = parse_dim_str(req.th_str, 60, 60)
    th_out, th_in = parts_th[0], parts_th[1]

    # --- 内外开框宽分配 ---
    if req.sel_nk == "内开":
        lwf, rwf = left_in, right_in
        lwb, rwb = left_out, right_out
        ftf, ftb = fw_top_in, fw_top_out
        thf, thb = th_in, th_out
    else:
        lwf, rwf = left_out, right_out
        lwb, rwb = left_in, right_in
        ftf, ftb = fw_top_out, fw_top_in
        thf, thb = th_out, th_in

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

    # --- 下槛处理 ---
    if req.threshold_type == "平底槛":
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
    if req.door_type == "两定两开":
        dt_cn = "两定两开门"
    else:
        dt_cn = req.door_type

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
        "ST": req.st_val, "HYSL": req.hysl, "QH": qh_val,
        "MSHD": mshd_val, "HHXD": req.hhxd, "BZ": final_note,
        "DOOR_TYPE": req.door_type, "MOTHER_DOOR_WIDTH": req.mother_door_width,
        "MID_DOOR_WIDTH": req.mid_door_width, "PILLAR_WIDTH_STR": req.pillar_width_str,
        "HAS_PILLAR": req.has_pillar, "HYYS": req.sel_hys,
        "DXK": dxk_val, "GXK": gxk_val, "PXK": pdk_val, "MX": dt_cn,
        "QC_HEIGHT": qc_height_val, "HAS_MM": req.has_mm, "MM_HEIGHT": mm_height_val,
        "ZMKS": req.zmks, "FMKS": req.fmks
    }

    # --- check_map ---
    out_mark = "√" if req.has_outer else ""
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

    check_map = {
        "kx": req.sel_kx, "nk": req.sel_nk, "qc": req.sel_qc,
        "lz": "有" if req.has_pillar else "无",
        "bz": req.sel_bz, "hys": req.sel_hys,
        "mm": "有" if req.has_mm else "无",
        "OUTER": out_mark, "INNER": in_mark,
        "NK": nk_mark, "WK": wk_mark,
        "KX_RIGHT": kxr_mark, "KX_LEFT": kxl_mark,
        "LZ_YES": lz_y, "LZ_NO": lz_n,
        "MM_YES": mm_y, "MM_NO": mm_n,
        "QC_GLASS": qc_g, "QC_SEAL": qc_s,
        "BZ_QB": bz_q, "BZ_MX": bz_m,
        "GDK": gdk_m, "PDK": pdk_m,
        "threshold": req.threshold_type,
    }

    # --- draw_params ---
    trim_f = req.trim_front_in if req.has_outer else 0
    trim_b = req.trim_back_in if req.has_inner else 0

    draw_params = {
        "dw": dw, "dh": dh,
        "left_width_front": lwf, "right_width_front": rwf,
        "left_width_back": lwb, "right_width_back": rwb,
        "fw_top_front": ftf, "fw_top_back": ftb,
        "th_front": thf, "th_back": thb,
        "trim_front": trim_f, "trim_back": trim_b,
        "overlap": overlap,
        "door_type": req.door_type,
        "mother_door_width": req.mother_door_width,
        "mid_door_width": req.mid_door_width,
        "pillar_width_str": req.pillar_width_str,
        "has_pillar": req.has_pillar,
        "kx": req.sel_kx, "nk": req.sel_nk,
        "qc": req.sel_qc, "qc_height": qc_height_val,
        "has_mm": req.has_mm, "mm_height": mm_height_val,
        "hys": req.sel_hys, "hysl": req.hysl,
        "left_right_gap": parse_gap_str(req.left_right_gap_str, 0),
        "top_bottom_gap": parse_gap_str(req.top_bottom_gap_str, 0),
        "middle_gap": req.middle_gap,
        "use_light_size": req.use_light_size,
        "light_w": req.light_w, "light_h": req.light_h,
        "zmls": req.zmls, "fmls": req.fmls,
    }

    return info_map, check_map, draw_params


# ===================== API: CAD 图纸生成 =====================
@app.post("/api/generate_cad")
def generate_cad(req: CADRequest):
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
    raw_filename = f"排版图纸_{req.dhdw or 'weimingming'}.dxf"
    encoded_filename = quote(raw_filename)
    ascii_filename = "drawing.dxf"

    return StreamingResponse(
        bytes_io,
        media_type="application/dxf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_filename}"; '
                f"filename*=UTF-8''{encoded_filename}"
            )
        }
    )


# ===================== API: 用户登录 =====================
@app.post("/api/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user_info = user_db.authenticate(req.uid, req.pwd)
    if user_info:
        token = create_token(user_info["uid"])
        return LoginResponse(
            success=True,
            message="登录成功",
            user=user_info,
            token=token,
        )
    else:
        return LoginResponse(success=False, message="账号或密码错误！")


# ===================== API: 用户管理 =====================
@app.get("/api/users")
def list_users():
    """获取所有用户列表"""
    users = user_db.load_all_users()
    return {"users": users, "total": len(users)}


@app.post("/api/users")
def create_user(req: UserCreateRequest):
    """创建或更新用户"""
    if not req.uid or not req.name or not req.pwd:
        raise HTTPException(status_code=400, detail="请填写完整账号信息。")
    user_db.add_or_update_user(req.uid, req.pwd, req.role, req.name)
    return {"success": True, "message": f"成功保存账号: {req.uid}"}


@app.delete("/api/users/{uid}")
def delete_user(uid: str):
    """删除用户（admin 不可删）"""
    if uid == "admin":
        raise HTTPException(status_code=400, detail="系统内置管理员不可删除")
    user_db.delete_user(uid)
    return {"success": True, "message": f"已删除账号: {uid}"}


@app.put("/api/users/{uid}/reset-password")
def reset_password(uid: str, req: ResetPasswordRequest):
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
               offset: int = Query(0, ge=0, description="偏移量")):
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
def get_task(task_id: str):
    """获取单个任务详情"""
    task = task_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.post("/api/tasks", response_model=TaskResponse)
def create_task(req: TaskCreateRequest):
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
        "ref_img_b64": req.ref_img_b64,
        "drawing_img_b64": None,
        "review_feedback": ""
    }
    try:
        task_db.add_task(new_task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 返回完整任务（包含已还原的图片）
    return task_db.get_task(task_id)


@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, req: TaskUpdateRequest):
    """更新任务（状态流转、上传图纸、提交审核意见等）"""
    existing = task_db.get_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="任务不存在")

    update_data = {}
    if req.status is not None:
        update_data["status"] = req.status
    if req.params is not None:
        update_data["params"] = req.params
    if req.drawing_img_b64 is not None:
        update_data["drawing_img_b64"] = req.drawing_img_b64
    if req.review_feedback is not None:
        update_data["review_feedback"] = req.review_feedback

    try:
        task_db.update_task(task_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return task_db.get_task(task_id)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
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
def admin_list_all_tasks():
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


# ===================== 健康检查 =====================
@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "西州将军铜门 - 协同平台 API"}


# ===================== 启动入口 =====================
if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
