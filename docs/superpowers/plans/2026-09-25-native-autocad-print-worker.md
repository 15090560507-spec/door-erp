# AutoCAD 原生 JPG 打印节点实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用当前 Windows 电脑上的 AutoCAD 2022 生成与手工打印一致的 `5940 x 4200` JPG，并让腾讯云 ERP 可靠排队、恢复和下载打印任务，同时恢复轻量 CAD 预览速度。

**Architecture:** 腾讯云 FastAPI 保存打印任务、DXF 和结果，Windows 助手通过出站 HTTPS 轮询并调用 `accoreconsole.exe`。AutoLISP 从 `ORDER_FORM` 块取得窗口范围并调用 AutoCAD 原生 Plot API；前端仅创建任务并轮询状态，SVG 预览与原生打印完全隔离。

**Tech Stack:** FastAPI、Pydantic、JSON 原子存储、React/Next.js、TypeScript、Python `requests`、AutoCAD 2022 Core Console、AutoLISP。

---

## 文件结构

- Create: `backend/cad_printing/__init__.py` — 导出打印路由。
- Create: `backend/cad_printing/models.py` — 打印任务和 Worker 请求模型。
- Create: `backend/cad_printing/database.py` — 原子保存任务、心跳、租约和状态迁移。
- Create: `backend/cad_printing/storage.py` — 保存 DXF/JPG 并校验安全路径。
- Create: `backend/cad_printing/routes.py` — 员工端和打印节点端 API。
- Modify: `backend/main.py` — 注册打印路由并注入现有 DXF 生成函数；移除 Matplotlib JPG 接口。
- Create: `backend/test_cad_print_queue.py` — 队列、租约、鉴权、上传和离线测试。
- Create: `tools/cad_print_worker/worker.py` — Windows 轮询、Core Console 调用和上传。
- Create: `tools/cad_print_worker/autocad_plot.lsp` — 原生打印 `ORDER_FORM`。
- Create: `tools/cad_print_worker/config.example.json` — 本地助手配置模板。
- Create: `tools/cad_print_worker/install-startup.ps1` — 安装开机启动任务。
- Create: `tools/cad_print_worker/test_worker.py` — Worker 单元测试。
- Create: `frontend/src/lib/cadPrintApi.ts` — 打印任务 API 和类型。
- Modify: `frontend/src/app/dashboard/page.tsx` — 打印进度、下载、离线状态和预览加速。
- Modify: `frontend/src/lib/api.ts` — 移除旧的同步 Matplotlib JPG API。
- Modify: `backend/requirements.txt` — 移除只为旧打印引擎增加的 Matplotlib。
- Delete: `backend/rendering/cad_sheet_jpg.py` — 删除近似正式打印实现。
- Delete: `backend/test_cad_sheet_jpg.py` — 由原生打印链路测试替代。
- Modify: `.env.example` — 增加打印节点令牌和租约配置。
- Modify: `docker-compose.yml` — 向后端传入打印节点配置。
- Create: `docs/native-autocad-print-worker.md` — Windows 安装、运行和故障排查。

### Task 1: 打印任务数据库与租约

**Files:**
- Create: `backend/cad_printing/__init__.py`
- Create: `backend/cad_printing/models.py`
- Create: `backend/cad_printing/database.py`
- Test: `backend/test_cad_print_queue.py`

- [ ] **Step 1: 编写失败测试，覆盖任务创建、领取、租约回收和心跳**

```python
def test_claim_is_single_and_expired_lease_returns_to_queue(tmp_path):
    db = CadPrintDatabase(tmp_path / "jobs.json", tmp_path / "nodes.json", lease_seconds=30)
    job = db.create_job(source_task_id="task-1", fingerprint="abc", dxf_path="a/source.dxf", created_by="A")
    claimed = db.claim_next("win-main", now="2026-09-25T10:00:00Z")
    assert claimed["id"] == job["id"]
    assert claimed["status"] == "claimed"
    assert db.claim_next("win-other", now="2026-09-25T10:00:10Z") is None
    reclaimed = db.claim_next("win-main", now="2026-09-25T10:00:31Z")
    assert reclaimed["id"] == job["id"]


def test_node_online_uses_last_heartbeat(tmp_path):
    db = CadPrintDatabase(tmp_path / "jobs.json", tmp_path / "nodes.json", offline_seconds=45)
    db.heartbeat("win-main", {"autocadReady": True}, now="2026-09-25T10:00:00Z")
    assert db.node_status("win-main", now="2026-09-25T10:00:40Z")["online"] is True
    assert db.node_status("win-main", now="2026-09-25T10:00:46Z")["online"] is False
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest backend/test_cad_print_queue.py -q`

Expected: FAIL，提示 `cad_printing.database` 不存在。

- [ ] **Step 3: 实现固定状态模型和原子 JSON 数据库**

`backend/cad_printing/models.py` 定义：

```python
from typing import Any, Literal
from pydantic import BaseModel, Field

CadPrintStatus = Literal["queued", "claimed", "printing", "uploading", "completed", "failed", "cancelled"]

class CadPrintCreateRequest(BaseModel):
    params: dict[str, Any]
    sourceTaskId: str = ""

class WorkerHeartbeatRequest(BaseModel):
    deviceId: str = Field(min_length=1, max_length=80)
    autocadReady: bool
    message: str = ""

class WorkerStatusRequest(BaseModel):
    deviceId: str
    status: Literal["printing", "uploading", "failed"]
    errorStage: str = ""
    errorMessage: str = ""
    logTail: str = ""
```

`backend/cad_printing/database.py` 实现 `create_job()`、`get_job()`、`list_jobs()`、`heartbeat()`、`node_status()`、`claim_next()`、`update_worker_status()`、`complete_job()` 和租约超时回队列。所有写入必须在单个锁中完成并使用临时文件加 `os.replace()`。

- [ ] **Step 4: 运行数据库测试**

Run: `python -m pytest backend/test_cad_print_queue.py -q`

Expected: PASS。

- [ ] **Step 5: 提交任务数据库**

```bash
git add backend/cad_printing backend/test_cad_print_queue.py
git commit -m "feat: add cad print job queue"
```

### Task 2: 文件存储、Worker 鉴权与打印 API

**Files:**
- Create: `backend/cad_printing/storage.py`
- Create: `backend/cad_printing/routes.py`
- Modify: `backend/main.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Test: `backend/test_cad_print_queue.py`

- [ ] **Step 1: 增加失败测试，覆盖设备令牌、DXF 下载、状态更新和 JPG 上传**

```python
def test_worker_endpoints_require_device_token(client, employee_headers, configured_generator):
    created = client.post("/api/cad-print/jobs", json={"params": {"dhdw": "测试"}}, headers=employee_headers)
    assert created.status_code == 200
    assert client.post("/api/cad-print/worker/claim", json={"deviceId": "win-main"}).status_code == 401


def test_worker_can_claim_download_and_upload_native_jpg(client, employee_headers, worker_headers, jpeg_5940x4200):
    job = client.post("/api/cad-print/jobs", json={"params": {"dhdw": "测试"}}, headers=employee_headers).json()["job"]
    claimed = client.post("/api/cad-print/worker/claim", json={"deviceId": "win-main"}, headers=worker_headers).json()["job"]
    assert claimed["id"] == job["id"]
    assert client.get(f"/api/cad-print/worker/jobs/{job['id']}/dxf", headers=worker_headers).content.startswith(b"0\nSECTION")
    uploaded = client.post(
        f"/api/cad-print/worker/jobs/{job['id']}/result",
        data={"deviceId": "win-main"},
        files={"file": ("result.jpg", jpeg_5940x4200, "image/jpeg")},
        headers=worker_headers,
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["job"]["status"] == "completed"
```

- [ ] **Step 2: 运行新增测试并确认失败**

Run: `python -m pytest backend/test_cad_print_queue.py -q`

Expected: FAIL，API 路由不存在。

- [ ] **Step 3: 实现安全文件存储**

`backend/cad_printing/storage.py` 只允许任务 ID 组成目录名，并提供：

```python
import io
import os
import re
from PIL import Image
from config import DATA_DIR

ROOT = os.path.join(DATA_DIR, "cad_print")
SAFE_ID = re.compile(r"^[a-f0-9]{12,40}$")

def _job_dir(job_id: str) -> str:
    if not SAFE_ID.fullmatch(job_id):
        raise ValueError("非法打印任务编号")
    path = os.path.join(ROOT, job_id)
    os.makedirs(path, exist_ok=True)
    return path

def dxf_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "source.dxf")

def result_path(job_id: str) -> str:
    return os.path.join(_job_dir(job_id), "result.jpg")

def save_dxf(job_id: str, content: bytes) -> str:
    path = dxf_path(job_id)
    with open(path, "wb") as handle:
        handle.write(content)
    return path

def save_result(job_id: str, content: bytes) -> tuple[str, int, int]:
    with Image.open(io.BytesIO(content)) as image:
        image.verify()
    with Image.open(io.BytesIO(content)) as image:
        width, height = image.size
    if (width, height) != (5940, 4200):
        raise ValueError(f"打印结果尺寸错误：{width}x{height}")
    path = result_path(job_id)
    with open(path, "wb") as handle:
        handle.write(content)
    return path, width, height
```

`save_result()` 使用 Pillow 验证 JPEG 可读取且尺寸严格为 `(5940, 4200)`，否则抛出 `ValueError`。

- [ ] **Step 4: 实现路由和单用途设备令牌**

`backend/cad_printing/routes.py` 暴露：

```text
POST /api/cad-print/jobs
GET  /api/cad-print/jobs/{job_id}
GET  /api/cad-print/jobs?sourceTaskId=<drawing-task-id>
GET  /api/cad-print/node-status
POST /api/cad-print/worker/heartbeat
POST /api/cad-print/worker/claim
GET  /api/cad-print/worker/jobs/{job_id}/dxf
POST /api/cad-print/worker/jobs/{job_id}/status
POST /api/cad-print/worker/jobs/{job_id}/result
```

Worker 路由使用 `hmac.compare_digest(request.headers["X-CAD-PRINT-TOKEN"], configured_token)`，不接受员工 JWT 代替设备令牌。员工端路由继续使用 `get_current_user`。

- [ ] **Step 5: 注入现有 DXF 生成函数并注册路由**

`backend/main.py`：

```python
from cad_printing.routes import cad_print_router, configure_cad_generator

def _generate_cad_for_print(params: dict) -> tuple[str, bytes]:
    request = CADRequest(**params)
    _validate_task_params(request.model_dump())
    key, dxf_bytes, _ = _cached_cad(request)
    return key, dxf_bytes

configure_cad_generator(_generate_cad_for_print)
app.include_router(cad_print_router)
```

- [ ] **Step 6: 增加环境变量**

`.env.example` 和 `docker-compose.yml` 增加：

```env
CAD_PRINT_DEVICE_TOKEN=replace-with-a-long-random-token
CAD_PRINT_LEASE_SECONDS=300
CAD_PRINT_NODE_OFFLINE_SECONDS=45
CAD_PRINT_DEVICE_ID=win-main
```

- [ ] **Step 7: 运行 API 测试**

Run: `python -m pytest backend/test_cad_print_queue.py -q`

Expected: PASS，错误令牌返回 401，错误尺寸 JPG 返回 422。

- [ ] **Step 8: 提交打印 API**

```bash
git add backend/cad_printing backend/main.py backend/test_cad_print_queue.py .env.example docker-compose.yml
git commit -m "feat: expose native cad print queue api"
```

### Task 3: Windows 打印助手协议与故障恢复

**Files:**
- Create: `tools/cad_print_worker/worker.py`
- Create: `tools/cad_print_worker/config.example.json`
- Create: `tools/cad_print_worker/test_worker.py`

- [ ] **Step 1: 编写失败测试，模拟领取、打印、上传和失败回报**

```python
def test_worker_claims_prints_and_uploads(tmp_path, fake_api, fake_runner):
    worker = CadPrintWorker(fake_api.config(tmp_path), api=fake_api, runner=fake_runner)
    assert worker.run_once() == "completed"
    assert fake_runner.calls[0].job_id == "job-1"
    assert fake_api.uploaded == ["job-1"]


def test_worker_reports_autocad_failure(tmp_path, fake_api, failing_runner):
    worker = CadPrintWorker(fake_api.config(tmp_path), api=fake_api, runner=failing_runner)
    assert worker.run_once() == "failed"
    assert fake_api.status_updates[-1]["errorStage"] == "autocad_plot"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tools/cad_print_worker/test_worker.py -q`

Expected: FAIL，`CadPrintWorker` 尚不存在。

- [ ] **Step 3: 实现 Worker 主循环**

`worker.py` 提供明确边界：

```python
@dataclass(frozen=True)
class WorkerConfig:
    base_url: str
    token: str
    device_id: str
    autocad_console: str
    poll_seconds: int = 5
    work_dir: str = "work"

class CadPrintWorker:
    def run_once(self) -> str:
        probe = self.runner.probe()
        self.api.heartbeat(self.config.device_id, probe)
        if not probe["autocadReady"]:
            return "not_ready"
        job = self.api.claim(self.config.device_id)
        if not job:
            return "idle"
        job_dir = Path(self.config.work_dir) / job["id"]
        job_dir.mkdir(parents=True, exist_ok=True)
        dxf_path = job_dir / "source.dxf"
        jpg_path = job_dir / "result.jpg"
        self.api.download_dxf(job["id"], dxf_path)
        try:
            self.api.update_status(job["id"], self.config.device_id, "printing")
            self.runner.print_job(job["id"], dxf_path, jpg_path)
            self.api.update_status(job["id"], self.config.device_id, "uploading")
            self.api.upload_result(job["id"], self.config.device_id, jpg_path)
            shutil.rmtree(job_dir)
            return "completed"
        except WorkerError as exc:
            self.api.fail(job["id"], self.config.device_id, exc.stage, str(exc), exc.log_tail)
            return "failed"

    def run_forever(self) -> None:
        while True:
            self.run_once()
            time.sleep(self.config.poll_seconds)

class AutoCadRunner:
    def print_job(self, job_id: str, dxf_path: Path, output_path: Path) -> Path:
        script_path = dxf_path.with_suffix(".scr")
        script_path.write_text(
            f'(load "{self.lisp_path.as_posix()}")\n(erp-print-order-form)\n',
            encoding="ascii",
        )
        command, env = self.build_command(dxf_path, output_path, script_path)
        result = subprocess.run(command, env=env, timeout=180, capture_output=True, text=True)
        log_tail = (result.stdout + "\n" + result.stderr)[-8000:]
        if result.returncode != 0 or "ERP_PRINT_ERROR:" in log_tail:
            raise WorkerError("autocad_plot", "AutoCAD 原生打印失败", log_tail)
        if not output_path.exists():
            raise WorkerError("jpg_missing", "AutoCAD 未生成 JPG", log_tail)
        with Image.open(output_path) as image:
            if image.size != (5940, 4200):
                raise WorkerError("jpg_size", f"JPG 尺寸为 {image.size[0]}x{image.size[1]}", log_tail)
        return output_path
```

每轮顺序固定为：检查 AutoCAD → 心跳 → 领取 → 下载 DXF → 更新 `printing` → 原生打印 → 校验尺寸 → 更新 `uploading` → 上传 → 清理临时目录。网络上传失败保留 JPG 并重试，不重复运行 AutoCAD。

- [ ] **Step 4: 写入不含密钥的配置模板**

```json
{
  "baseUrl": "https://your-domain.example.com/api",
  "deviceId": "win-main",
  "deviceTokenEnv": "CAD_PRINT_DEVICE_TOKEN",
  "autocadConsole": "D:\\Desin all\\CAD2022\\AutoCAD 2022\\accoreconsole.exe",
  "pollSeconds": 5,
  "workDir": "D:\\door-erp-cad-print-work"
}
```

- [ ] **Step 5: 运行 Worker 单元测试**

Run: `python -m pytest tools/cad_print_worker/test_worker.py -q`

Expected: PASS，测试中不实际启动 AutoCAD。

- [ ] **Step 6: 提交 Worker 协议**

```bash
git add tools/cad_print_worker
git commit -m "feat: add windows cad print worker"
```

### Task 4: AutoCAD 原生 ORDER_FORM 打印脚本

**Files:**
- Create: `tools/cad_print_worker/autocad_plot.lsp`
- Modify: `tools/cad_print_worker/worker.py`
- Modify: `tools/cad_print_worker/test_worker.py`

- [ ] **Step 1: 增加 Runner 命令测试**

```python
def test_autocad_command_uses_input_script_and_output_environment(tmp_path, monkeypatch):
    runner = AutoCadRunner(console_path=Path(r"D:\Desin all\CAD2022\AutoCAD 2022\accoreconsole.exe"))
    command, env = runner.build_command(tmp_path / "source.dxf", tmp_path / "result.jpg", tmp_path / "plot.scr")
    assert command[1:5] == ["/i", str(tmp_path / "source.dxf"), "/s", str(tmp_path / "plot.scr")]
    assert env["ERP_JPG_PATH"].endswith("result.jpg")
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tools/cad_print_worker/test_worker.py -q`

Expected: FAIL，`build_command()` 尚未实现。

- [ ] **Step 3: 实现 AutoLISP 原生打印**

`autocad_plot.lsp` 必须：

1. 遍历模型空间块参照，使用 `EffectiveName` 查找 `ORDER_FORM` 或 `ORDERFORM`。
2. 使用 `vla-GetBoundingBox` 获得窗口左下角和右上角。
3. 对当前布局设置 `PublishToWeb JPG.pc3`、`monochrome.ctb`、窗口、居中、布满图纸、横向、线宽和打印样式。
4. 从环境变量 `ERP_JPG_PATH` 取得输出位置。
5. 调用 `PlotToFile`，失败时输出以 `ERP_PRINT_ERROR:` 开头的错误。

核心调用保持如下：

```lisp
(vla-put-ConfigName layout "PublishToWeb JPG.pc3")
(vla-RefreshPlotDeviceInfo layout)
(vla-put-PlotType layout 4)
(vla-SetWindowToPlot layout min-point max-point)
(vla-put-CenterPlot layout :vlax-true)
(vla-put-UseStandardScale layout :vlax-true)
(vla-put-StandardScale layout 0)
(vla-put-PlotRotation layout 1)
(vla-put-StyleSheet layout "monochrome.ctb")
(vla-put-PlotWithLineweights layout :vlax-true)
(vla-put-PlotWithPlotStyles layout :vlax-true)
(vla-PlotToFile (vla-get-Plot doc) output-path "PublishToWeb JPG.pc3")
```

脚本必须从设备返回的 canonical media names 中查找同时包含 `5940` 和 `4200` 的介质；不存在时失败，不静默改成其他尺寸。

- [ ] **Step 4: 实现 Core Console 启动、超时和日志捕获**

`AutoCadRunner.print_job()` 使用 `subprocess.run(command, env=env, timeout=180, capture_output=True, text=True)`。退出码非零、日志含 `ERP_PRINT_ERROR:` 或 JPG 不存在均抛出带阶段信息的异常。

- [ ] **Step 5: 运行 Worker 测试**

Run: `python -m pytest tools/cad_print_worker/test_worker.py -q`

Expected: PASS。

- [ ] **Step 6: 在当前 Windows 电脑执行真实集成测试**

Run:

```powershell
python tools\cad_print_worker\worker.py --self-test --dxf data\cad-print-self-test.dxf --output data\cad-print-self-test.jpg
```

Expected:

- 实际启动 `D:\Desin all\CAD2022\AutoCAD 2022\accoreconsole.exe`。
- 输出文件存在且为 `5940 x 4200`。
- 日志显示找到 `ORDER_FORM`、PC3、CTB 和对应介质。
- 目视检查无黑块、中文无方块、字体与 AutoCAD 图形界面打印一致。

- [ ] **Step 7: 提交 AutoCAD 打印脚本**

```bash
git add tools/cad_print_worker
git commit -m "feat: print order form with autocad core console"
```

### Task 5: 前端打印任务与节点状态

**Files:**
- Create: `frontend/src/lib/cadPrintApi.ts`
- Modify: `frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: 定义前端类型和 API**

`cadPrintApi.ts`：

```typescript
export type CadPrintStatus = "queued" | "claimed" | "printing" | "uploading" | "completed" | "failed" | "cancelled";

export interface CadPrintJob {
  id: string;
  sourceTaskId: string;
  status: CadPrintStatus;
  resultUrl?: string;
  errorStage?: string;
  errorMessage?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CadPrintNodeStatus {
  deviceId: string;
  online: boolean;
  autocadReady: boolean;
  message: string;
  lastSeenAt?: string;
}

export async function createCadPrintJob(params: DoorFormData, sourceTaskId: string): Promise<CadPrintJob> {
  const { data } = await api.post<{ job: CadPrintJob }>("/cad-print/jobs", { params, sourceTaskId });
  return data.job;
}

export async function getCadPrintJob(jobId: string): Promise<CadPrintJob> {
  const { data } = await api.get<{ job: CadPrintJob }>(`/cad-print/jobs/${jobId}`);
  return data.job;
}

export async function getCadPrintNodeStatus(): Promise<CadPrintNodeStatus> {
  const { data } = await api.get<{ node: CadPrintNodeStatus }>("/cad-print/node-status");
  return data.node;
}
```

- [ ] **Step 2: 将同步下载按钮改为后台任务状态**

`dashboard/page.tsx` 增加 `cadPrintJob`、`cadPrintLoading`、`cadPrintNode` 和轮询 effect。按钮文案按状态显示：

```typescript
const CAD_PRINT_LABELS: Record<CadPrintStatus, string> = {
  queued: "等待打印节点",
  claimed: "节点已领取",
  printing: "AutoCAD 打印中",
  uploading: "正在上传",
  completed: "下载原生 JPG",
  failed: "打印失败，点击重试",
  cancelled: "任务已取消",
};
```

完成时保留“下载原生 JPG”按钮，并只自动下载一次；离线时在按钮旁显示“打印节点离线，电脑开机后会自动继续”。

- [ ] **Step 3: 运行前端构建**

Run: `cd frontend && npm run build`

Expected: TypeScript 和 Next.js 构建通过。

- [ ] **Step 4: 提交前端打印流程**

```bash
git add frontend/src/lib/cadPrintApi.ts frontend/src/app/dashboard/page.tsx
git commit -m "feat: show native cad print job progress"
```

### Task 6: 恢复轻量 CAD 预览速度

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`
- Test: `backend/test_cad_line_art_ratio.py`

- [ ] **Step 1: 删除预览按钮中的重复 DXF 下载请求**

将 `handleGeneratePreview()` 调整为只调用：

```typescript
const svg = await generateCadPreview(formData);
setCadPreviewSvg(svg);
setCadBlob(null);
setCadBlobFingerprint("");
```

不得在该函数内调用 `generateCad()`、`generateCadJpg()` 或创建打印任务。

- [ ] **Step 2: 保留后端 DXF 和 SVG 独立缓存指标**

确认 `/api/generate_cad_preview` 仍返回：

```text
X-CAD-Cache: HIT|MISS
X-CAD-Preview-Cache: HIT|MISS
```

并为同一参数连续两次请求增加测试，第二次两个响应头均为 `HIT`。

- [ ] **Step 3: 运行预览测试和前端构建**

Run:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/test_cad_line_art_ratio.py -q
Set-Location frontend
npm run build
```

Expected: 测试和构建通过。

- [ ] **Step 4: 提交预览性能修复**

```bash
git add frontend/src/app/dashboard/page.tsx backend/test_cad_line_art_ratio.py
git commit -m "perf: avoid duplicate cad generation for preview"
```

### Task 7: 删除近似正式打印实现

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`
- Modify: `frontend/src/lib/api.ts`
- Delete: `backend/rendering/cad_sheet_jpg.py`
- Delete: `backend/test_cad_sheet_jpg.py`

- [ ] **Step 1: 将旧接口改为明确的迁移错误或直接删除**

删除 `/api/generate_cad_jpg` 以及 `_cached_cad_sheet_jpg()`。若兼容旧前端需要短期保留路由，则返回 HTTP 410：

```python
raise HTTPException(status_code=410, detail="请使用 AutoCAD 原生打印任务接口")
```

- [ ] **Step 2: 删除 Matplotlib 打印器和前端同步 JPG 方法**

删除 `rendering/cad_sheet_jpg.py`、对应测试、`generateCadJpg()` 以及 `matplotlib` 依赖。不得保留静默近似回退。

- [ ] **Step 3: 运行后端相关回归测试**

Run:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/test_cad_print_queue.py backend/test_cad_line_art_ratio.py backend/test_render_background_task.py -q
```

Expected: PASS，运行日志中不导入 Matplotlib。

- [ ] **Step 4: 提交旧实现清理**

```bash
git add backend/main.py backend/requirements.txt frontend/src/lib/api.ts backend/rendering/cad_sheet_jpg.py backend/test_cad_sheet_jpg.py
git commit -m "refactor: remove approximate cad jpg renderer"
```

### Task 8: Windows 开机启动、部署文档和端到端验收

**Files:**
- Create: `tools/cad_print_worker/install-startup.ps1`
- Create: `docs/native-autocad-print-worker.md`
- Modify: `tools/cad_print_worker/worker.py`

- [ ] **Step 1: 实现开机启动安装脚本**

`install-startup.ps1` 创建名为 `DoorERP-CadPrintWorker` 的计划任务，使用当前用户登录时启动，工作目录固定为仓库根目录；脚本支持 `-Uninstall` 删除任务。令牌从用户级环境变量读取，不写入计划任务参数。

- [ ] **Step 2: 编写安装与故障排查文档**

文档必须包含：

```powershell
$env:CAD_PRINT_DEVICE_TOKEN="与腾讯云相同的长随机令牌"
python tools\cad_print_worker\worker.py --config tools\cad_print_worker\config.json
powershell -ExecutionPolicy Bypass -File tools\cad_print_worker\install-startup.ps1
```

同时说明如何检查 AutoCAD 路径、节点在线状态、PC3/CTB、任务日志、离线排队和重新上传。

- [ ] **Step 3: 执行完整自动化测试**

Run:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/test_cad_print_queue.py backend/test_cad_line_art_ratio.py backend/test_render_background_task.py tools/cad_print_worker/test_worker.py -q
Set-Location frontend
npm run build
```

Expected: 全部 PASS，前端构建成功。

- [ ] **Step 4: 执行端到端原生打印验收**

1. 启动本地 FastAPI。
2. 启动 Windows 打印助手。
3. 在图纸页面点击“打印 JPG”。
4. 观察状态依次经过 `queued`、`claimed`、`printing`、`uploading`、`completed`。
5. 下载并确认 `5940 x 4200`、无黑块、中文无方块、图框比例正确。
6. 停止 Worker 后再提交一张图，确认状态保持 `queued`；恢复 Worker 后自动完成。

- [ ] **Step 5: 提交部署与验收资料**

```bash
git add tools/cad_print_worker/install-startup.ps1 tools/cad_print_worker/worker.py docs/native-autocad-print-worker.md
git commit -m "docs: add native cad print worker deployment"
```

- [ ] **Step 6: 推送既定 GitHub 分支**

Run: `git push origin HEAD:feat/semicircle-handles-and-quote-form-improvements`

Expected: 远端分支更新到最终提交；`data/users_database.json` 等运行数据不进入提交。
