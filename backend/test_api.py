#!/usr/bin/env python
"""
Test script: 验证 /api/generate_cad 接口是否能成功返回 DXF 文件
用法:
  1. 先启动后端: cd F:\Door && python -m backend.main
  2. 再运行测试: python backend/test_api.py
  或直接用单一命令测试:
  3. python backend/test_api.py --auto  (自动启动/停止服务)
"""
import sys
import os
import json
import time
import subprocess
import tempfile

# 确保能找到 backend 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests


def build_test_payload():
    """构造一个完整的测试 CAD 请求数据"""
    return {
        "dhdw": "测试客户有限公司",
        "gdmc": "测试工程项目",
        "ddh": "ORD-2024-001",
        "sl": "2 樘",
        "hhxd": "D",
        "dhrq": "2026.05.03",
        "zzcl": "1.0的不锈钢镀铜",
        "ys": "仿古铜",
        "zmks": "按图",
        "fmks": "按图",
        "mshd": 80,
        "qh": "240",
        "sel_bz": "全包",
        "door_type": "单门",
        "sel_kx": "右开",
        "sel_nk": "内开",
        "use_light_size": False,
        "dw": 960,
        "dh": 2100,
        "light_w": 0,
        "light_h": 0,
        "mother_door_width": 600,
        "mid_door_width": 400,
        "fw_left_str": "60/60",
        "fw_right_str": "60/60",
        "fw_top_str": "60/60",
        "threshold_type": "高低槛",
        "th_str": "55/70",
        "pdk": "60",
        "zmls": "标配拉手",
        "fmls": "标配拉手",
        "st_val": "标准锁体",
        "sel_hys": "葫芦头合页",
        "hysl": "3个/扇",
        "has_outer": True,
        "has_inner": False,
        "overlap": 20,
        "trim_front_in": 160,
        "trim_back_in": 140,
        "sel_qc": "无",
        "has_mm": False,
        "has_pillar": False,
        "qc_height": 400,
        "mm_height": 200,
        "pillar_width_str": "55/70",
        "sm": "测试数据 - 车间批注",
        "left_right_gap_str": "0/0",
        "top_bottom_gap_str": "0/0",
        "middle_gap": 0
    }


def test_generate_cad(base_url="http://localhost:8000"):
    """测试 /api/generate_cad 接口"""
    print("=" * 60)
    print("测试 /api/generate_cad 接口")
    print("=" * 60)

    payload = build_test_payload()

    # 1. 发送请求
    print(f"\n[1] 发送 POST 请求到 {base_url}/api/generate_cad ...")
    print(f"    请求体大小: {len(json.dumps(payload, ensure_ascii=False))} bytes")

    try:
        resp = requests.post(
            f"{base_url}/api/generate_cad",
            json=payload,
            timeout=60
        )
    except requests.exceptions.ConnectionError:
        print("\n[FAIL] 无法连接到后端服务！")
        print("      请先启动后端: cd F:\\Door && python -m backend.main")
        return False

    # 2. 检查 HTTP 状态
    print(f"[2] HTTP 状态码: {resp.status_code}")
    if resp.status_code != 200:
        print(f"    错误响应: {resp.text[:500]}")
        print("[FAIL] 接口返回非 200 状态码！")
        return False

    # 3. 检查 Content-Type
    content_type = resp.headers.get("content-type", "")
    print(f"[3] Content-Type: {content_type}")

    # 4. 检查 Content-Disposition
    content_disp = resp.headers.get("content-disposition", "")
    print(f"[4] Content-Disposition: {content_disp}")

    # 5. 检查响应体大小
    body = resp.content
    print(f"[5] 响应体大小: {len(body)} bytes ({len(body)/1024:.1f} KB)")

    if len(body) < 100:
        print(f"[FAIL] 响应体过小 ({len(body)} bytes)，可能不是有效的 DXF 文件！")
        print(f"    内容: {body[:500]}")
        return False

    # 6. 检查 DXF 文件头（DXF 文件以特定文本开头）
    first_bytes = body[:20]
    print(f"[6] 文件头 (前20字节): {first_bytes}")

    # DXF binary 以 "AutoCAD Binary DXF" 开头，ASCII 以 "  0\r\nSECTION" 开头
    text_start = body[:50].decode('utf-8', errors='replace')
    print(f"    文本开头: {repr(text_start[:50])}")

    # 7. 保存到本地
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"test_door_output_{int(time.time())}.dxf")

    with open(output_path, 'wb') as f:
        f.write(body)
    print(f"[7] 已保存 DXF 文件到: {output_path}")

    print(f"\n{'=' * 60}")
    print("[PASS] /api/generate_cad 接口测试成功！")
    print(f"       生成的 DXF 文件: {output_path}")
    print(f"       文件大小: {len(body)} bytes ({len(body)/1024:.1f} KB)")
    print(f"{'=' * 60}")
    return True


def test_login(base_url="http://localhost:8000"):
    """测试登录接口"""
    print("\n" + "=" * 60)
    print("测试 /api/login 接口")
    print("=" * 60)

    # 正常登录
    resp = requests.post(f"{base_url}/api/login", json={"uid": "A", "pwd": "123"})
    print(f"[1] 正常登录 (A/123): HTTP {resp.status_code}, {resp.json()}")

    # 错误密码
    resp = requests.post(f"{base_url}/api/login", json={"uid": "A", "pwd": "wrong"})
    print(f"[2] 错误密码 (A/wrong): HTTP {resp.status_code}, {resp.json()}")

    return True


def test_tasks_crud(base_url="http://localhost:8000"):
    """测试任务 CRUD"""
    print("\n" + "=" * 60)
    print("测试任务管理接口")
    print("=" * 60)

    # 创建任务
    task_data = {
        "params": build_test_payload(),
        "ref_text": "请按图施工，注意包套宽度",
        "ref_img_b64": None
    }
    resp = requests.post(f"{base_url}/api/tasks", json=task_data)
    print(f"[1] 创建任务: HTTP {resp.status_code}")
    task = resp.json()
    task_id = task.get("id", "")
    print(f"    任务ID: {task_id}")

    # 获取任务列表
    resp = requests.get(f"{base_url}/api/tasks")
    print(f"[2] 获取任务列表: HTTP {resp.status_code}, 总数: {resp.json().get('total', 0)}")

    # 获取单个任务
    resp = requests.get(f"{base_url}/api/tasks/{task_id}")
    print(f"[3] 获取任务 {task_id}: HTTP {resp.status_code}")

    # 更新任务
    resp = requests.put(f"{base_url}/api/tasks/{task_id}", json={"status": "待初审"})
    print(f"[4] 更新任务状态: HTTP {resp.status_code}, 新状态: {resp.json().get('status')}")

    # 删除任务
    resp = requests.delete(f"{base_url}/api/tasks/{task_id}")
    print(f"[5] 删除任务: HTTP {resp.status_code}")

    return True


def start_server():
    """启动后端服务"""
    print("启动 FastAPI 后端服务...")
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(backend_dir)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=parent_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 等待服务启动
    time.sleep(3)
    return proc


def main():
    auto_mode = "--auto" in sys.argv

    server_proc = None
    try:
        if auto_mode:
            server_proc = start_server()

        # 测试接口
        all_pass = True

        all_pass &= test_login()
        all_pass &= test_tasks_crud()
        all_pass &= test_generate_cad()

        if all_pass:
            print("\n" + "=" * 60)
            print("全部测试通过！")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("存在测试失败！")
            print("=" * 60)
            sys.exit(1)

    finally:
        if server_proc:
            print("\n正在停止后端服务...")
            server_proc.terminate()
            server_proc.wait()


if __name__ == "__main__":
    main()
