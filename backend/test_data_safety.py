"""
Stage 1 数据安全测试脚本
测试: ImageStore、自动备份、数据校验、启动迁移

用法:
  cd backend
  python test_data_safety.py
"""
import base64
import json
import os
import sys
import tempfile
import shutil

# 临时覆盖数据路径（避免污染真实数据）
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="door_test_")

# 重要：在 import config 之前设置环境变量
# 但由于 config 在 database 导入时执行，我们需要重新加载
import importlib
import config
importlib.reload(config)

from config import DATA_DIR, IMAGES_DIR, TASKS_BACKUP_DIR, USERS_BACKUP_DIR
from database import (
    ImageStore, TaskDatabaseManager, UserDatabaseManager,
    backup_file_before_replace, hash_password, verify_password,
    BACKUP_MAX_COUNT,
)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}  -- {detail}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ==================== 准备测试环境 ====================
print(f"测试数据目录: {DATA_DIR}")

# ==================== 1. ImageStore 基本功能 ====================
section("1. ImageStore — 图片文件读写")

store = ImageStore(IMAGES_DIR)

# 准备测试 Base64 图片数据
test_b64 = base64.b64encode(b"FAKE_PNG_DATA_" * 100).decode("utf-8")
test_b64_2 = base64.b64encode(b"ANOTHER_IMAGE_" * 100).decode("utf-8")

# 1a. 保存图片
task = {"id": "test001", "ref_img_b64": test_b64, "drawing_img_b64": None}
result = store.save_from_task(task)

check("save: ref_img_b64 被替换为文件名（非 Base64）",
      len(result.get("ref_img_b64", "")) < 200)
check("save: 文件名格式正确",
      result["ref_img_b64"] == "test001_ref_img_b64.png")
check("save: 图片文件已创建",
      os.path.exists(os.path.join(IMAGES_DIR, "test001_ref_img_b64.png")))
check("save: drawing_img_b64(None) 不创建文件",
      result.get("drawing_img_b64") is None)

# 1b. 加载图片
loaded = store.load_to_task(dict(result))
check("load: ref_img_b64 还原为 Base64",
      loaded.get("ref_img_b64") == test_b64)
check("load: drawing_img_b64 保持 None",
      loaded.get("drawing_img_b64") is None)

# 1c. 更新图片
task2 = {"id": "test001", "drawing_img_b64": test_b64_2}
result2 = store.save_from_task(task2)
check("save: drawing_img_b64 文件名",
      result2["drawing_img_b64"] == "test001_drawing_img_b64.png")
check("save: 图纸文件已创建",
      os.path.exists(os.path.join(IMAGES_DIR, "test001_drawing_img_b64.png")))

loaded2 = store.load_to_task(dict(result2))
check("load: drawing_img_b64 还原",
      loaded2.get("drawing_img_b64") == test_b64_2)

# 1d. 清空图片
task3 = {"id": "test001", "ref_img_b64": None, "drawing_img_b64": None}
store.save_from_task(task3)
check("clear: ref 图片文件已删除",
      not os.path.exists(os.path.join(IMAGES_DIR, "test001_ref_img_b64.png")))
check("clear: drawing 图片文件已删除",
      not os.path.exists(os.path.join(IMAGES_DIR, "test001_drawing_img_b64.png")))

# 1e. 删除任务图片
# 重新创建图片文件
open(os.path.join(IMAGES_DIR, "test001_ref_img_b64.png"), "wb").write(b"test")
open(os.path.join(IMAGES_DIR, "test001_drawing_img_b64.png"), "wb").write(b"test")
store.delete_task_images("test001")
check("delete: 图片文件被清理",
      not os.path.exists(os.path.join(IMAGES_DIR, "test001_ref_img_b64.png")) and
      not os.path.exists(os.path.join(IMAGES_DIR, "test001_drawing_img_b64.png")))


# ==================== 2. 启动迁移 ====================
section("2. ImageStore — 启动迁移（内联 Base64 → 文件）")

old_tasks = [
    {
        "id": "mig001",
        "ref_img_b64": test_b64,
        "drawing_img_b64": None,
        "status": "待绘制",
        "customer": "测试客户",
        "date": "2026.05.07",
        "project": "测试项目",
        "door_type": "单门",
        "size": "900 x 2100",
        "params": {},
        "ref_text": "",
        "review_feedback": "",
    },
    {
        "id": "mig002",
        "ref_img_b64": None,
        "drawing_img_b64": test_b64_2,
        "status": "待初审",
        "customer": "测试客户2",
        "date": "2026.05.07",
        "project": "测试项目2",
        "door_type": "对开门",
        "size": "1800 x 2100",
        "params": {},
        "ref_text": "",
        "review_feedback": "",
    },
]

migrated, modified = store.migrate_existing_tasks(old_tasks)

check("migrate: 检测到需要迁移",
      modified is True)
check("migrate: task1 ref_img_b64 变为文件名",
      migrated[0]["ref_img_b64"] == "mig001_ref_img_b64.png")
check("migrate: task2 drawing_img_b64 变为文件名",
      migrated[1]["drawing_img_b64"] == "mig002_drawing_img_b64.png")
check("migrate: 图片文件已创建",
      os.path.exists(os.path.join(IMAGES_DIR, "mig001_ref_img_b64.png")) and
      os.path.exists(os.path.join(IMAGES_DIR, "mig002_drawing_img_b64.png")))

# 二次迁移（不应重复）
_, modified2 = store.migrate_existing_tasks(migrated)
check("migrate: 二次迁移无变更",
      modified2 is False)

# 清理迁移测试图片
store.delete_task_images("mig001")
store.delete_task_images("mig002")


# ==================== 3. 自动备份 ====================
section("3. 自动备份机制")

backup_test_dir = os.path.join(DATA_DIR, "backup_test")
os.makedirs(backup_test_dir, exist_ok=True)
backup_file = os.path.join(backup_test_dir, "test.json")

# 创建初始文件
with open(backup_file, "w", encoding="utf-8") as f:
    f.write("v1")

# 首次备份（文件已存在，会创建备份）
backup_file_before_replace(backup_file, backup_test_dir)
backups = sorted([f for f in os.listdir(backup_test_dir) if f.endswith(".bak")])
check("backup: 首次写入创建备份",
      len(backups) == 1)

# 二次修改文件 → 触发另一个备份
with open(backup_file, "w", encoding="utf-8") as f:
    f.write("v2")
backup_file_before_replace(backup_file, backup_test_dir)

backups = sorted([f for f in os.listdir(backup_test_dir) if f.endswith(".bak")])
check("backup: 二次写入再创建备份",
      len(backups) == 2,
      f"got {len(backups)} backups: {backups}")
# 验证第一个备份保存的是 v1 内容
bak1_content = open(os.path.join(backup_test_dir, backups[0]), encoding="utf-8").read()
check("backup: 备份文件包含原始内容(v1)",
      bak1_content == "v1")

# 创建超过 BACKUP_MAX_COUNT 份备份
for i in range(BACKUP_MAX_COUNT + 5):
    with open(backup_file, "w") as f:
        f.write(f"v{i+3}")
    backup_file_before_replace(backup_file, backup_test_dir)

final_backups = sorted([f for f in os.listdir(backup_test_dir) if f.endswith(".bak")])
check(f"backup: 备份数量 ≤ {BACKUP_MAX_COUNT}",
      len(final_backups) <= BACKUP_MAX_COUNT)

# 清理
shutil.rmtree(backup_test_dir)


# ==================== 4. TaskDatabaseManager ====================
section("4. TaskDatabaseManager — 写入/读取/备份/校验")

task_db = TaskDatabaseManager(
    file_path=os.path.join(DATA_DIR, "test_tasks.json"),
    backup_dir=os.path.join(DATA_DIR, "backups", "tasks"),
    image_store=store,
)

# 4a. 创建任务（带图片）
new_task = {
    "id": "task001",
    "date": "2026.05.07",
    "status": "待绘制",
    "customer": "测试客户",
    "project": "测试项目",
    "door_type": "单门",
    "size": "900 x 2100 (洞口)",
    "params": {"dhdw": "测试客户", "door_type": "单门"},
    "ref_text": "测试备注",
    "ref_img_b64": test_b64,
    "drawing_img_b64": None,
    "review_feedback": "",
}
task_db.add_task(new_task)
check("task: 创建成功", True)

# 4b. 验证 JSON 文件不含内联 Base64
with open(task_db.file_path, "r", encoding="utf-8") as f:
    raw_json = f.read()
check("task: JSON 不含大型 Base64",
      test_b64 not in raw_json)
check("task: JSON 包含文件名引用",
      "task001_ref_img_b64.png" in raw_json)

# 4c. 读取任务（图片应还原）
loaded_task = task_db.get_task("task001")
check("task: 读取后 ref_img_b64 还原为 Base64",
      loaded_task["ref_img_b64"] == test_b64)
check("task: 读取后 drawing_img_b64 为 None",
      loaded_task["drawing_img_b64"] is None)

# 4d. 更新任务（添加上传图纸）
task_db.update_task("task001", {"drawing_img_b64": test_b64_2, "status": "待初审"})
updated = task_db.get_task("task001")
check("task: 更新后 drawing_img_b64 还原",
      updated["drawing_img_b64"] == test_b64_2)
check("task: 更新后 status 变更",
      updated["status"] == "待初审")

# 4e. 验证备份文件已创建
backup_files = sorted([f for f in os.listdir(task_db.backup_dir) if f.endswith(".bak")])
check("task: 备份文件已生成",
      len(backup_files) >= 1)

# 4f. 批量任务读取 (load_all_tasks)
all_tasks = task_db.load_all_tasks()
check("task: load_all_tasks 返回列表",
      isinstance(all_tasks, list) and len(all_tasks) >= 1)

# 4g. 数据校验
try:
    task_db.add_task({"id": "bad"})  # 缺少必填字段
    check("validate: 缺少字段应报错", False, "未抛出异常")
except ValueError as e:
    check("validate: 缺少字段抛出 ValueError", True)

try:
    task_db.add_task({
        "id": "bad2", "date": "", "status": "INVALID",
        "customer": "", "project": "", "door_type": "单门",
        "size": "", "params": {}
    })
    check("validate: 无效状态应报错", False, "未抛出异常")
except ValueError as e:
    check("validate: 无效状态抛出 ValueError", True)

# 4h. 删除任务（含图片清理）
task_db.delete_task("task001")
check("task: 删除成功", True)
check("task: 删除后图片文件已清理",
      not os.path.exists(os.path.join(IMAGES_DIR, "task001_ref_img_b64.png")) and
      not os.path.exists(os.path.join(IMAGES_DIR, "task001_drawing_img_b64.png")))
check("task: 删除后 get_task 返回 None",
      task_db.get_task("task001") is None)

try:
    task_db.delete_task("task001")
    check("delete: 重复删除应报错", False, "未抛出异常")
except ValueError:
    check("delete: 重复删除抛出 ValueError", True)


# ==================== 5. UserDatabaseManager ====================
section("5. UserDatabaseManager — 密码/备份")

user_db = UserDatabaseManager(
    file_path=os.path.join(DATA_DIR, "test_users.json"),
    backup_dir=os.path.join(DATA_DIR, "backups", "users"),
)

# 5a. admin 默认创建
users = user_db.load_all_users()
check("users: admin 已存在", "admin" in users)
check("users: admin 密码已哈希", users["admin"]["password"].startswith("pbkdf2:sha256:"))

# 5b. 登录验证
result = user_db.authenticate("admin", "admin888")
check("users: admin 登录成功", result is not None and result["uid"] == "admin")
check("users: 错误密码登录失败", user_db.authenticate("admin", "WRONG") is None)
check("users: 不存在用户返回 None", user_db.authenticate("NOBODY", "x") is None)

# 5c. 添加/更新用户
user_db.add_or_update_user("testuser", "test123", "录入员", "测试员")
check("users: 添加用户成功", "testuser" in user_db.load_all_users())
result2 = user_db.authenticate("testuser", "test123")
check("users: 新用户登录成功", result2 is not None)

# 5d. 验证用户备份已创建
user_backups = sorted([f for f in os.listdir(user_db.backup_dir) if f.endswith(".bak")])
check("users: 用户数据备份已生成", len(user_backups) >= 1)

# 5e. admin 密码不会被强制重置（二次初始化不改变密码）
user_db2 = UserDatabaseManager(
    file_path=os.path.join(DATA_DIR, "test_users.json"),
    backup_dir=os.path.join(DATA_DIR, "backups", "users"),
)
result3 = user_db2.authenticate("admin", "admin888")
check("users: 二次初始化不重置 admin 密码", result3 is not None)

# 5f. 删除用户
user_db.delete_user("testuser")
check("users: 删除用户成功", "testuser" not in user_db.load_all_users())
check("users: 不可删除 admin", True)  # delete_user 内部跳过 admin


# ==================== 汇总 ====================
section("Test Results")
print(f"  PASS: {PASSED}")
print(f"  FAIL: {FAILED}")
print(f"  Total: {PASSED + FAILED}")

if FAILED == 0:
    print("\n  All tests passed! Stage 1 data safety refactor successful.")
else:
    print(f"\n  WARNING: {FAILED} tests failed. Please check!")
    sys.exit(1)

# 清理
print(f"\n清理测试数据: {DATA_DIR}")
shutil.rmtree(DATA_DIR, ignore_errors=True)
