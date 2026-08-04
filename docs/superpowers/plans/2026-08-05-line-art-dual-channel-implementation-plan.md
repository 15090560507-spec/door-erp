# Front And Back Line Art Dual-Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the render page obtain two independent, clean front/back line-art images from either an existing drawing task or an uploaded order-sheet image, then submit only the user-selected side through the unchanged render-task protocol.

**Architecture:** Add an authenticated line-art extraction service with two strategies: deterministic DXF-layer export for linked projects and OpenCV/OCR-assisted crop detection for uploaded sheets. Both strategies persist temporary lossless PNG files and return one shared response shape; the frontend owns source selection, review/crop correction, side selection, and conversion of the selected authenticated URL back into the existing `File` upload.

**Tech Stack:** FastAPI, Pydantic 2, ezdxf 1.4, Pillow, OpenCV headless, NumPy, Tesseract OCR, Next.js 16, React 19, TypeScript, existing JSON storage and render file routes.

---

## File Structure

- Create `backend/rendering/line_art.py`: shared extraction record lifecycle, normalized crop boxes, upload-sheet detection, OCR anchors, lossless crop output, and manual recrop.
- Create `backend/rendering/cad_line_art.py`: deterministic DXF primitive filtering and front/back PNG rendering.
- Modify `backend/rendering/models.py`: extraction request/response contracts.
- Modify `backend/rendering/database.py`: temporary extraction JSON table and CRUD methods.
- Modify `backend/rendering/routes.py`: upload extraction, extraction read, and crop-correction endpoints.
- Modify `backend/main.py`: task-linked extraction endpoint, reusing `task_db`, `CADRequest`, and `_cached_cad` without introducing circular imports.
- Modify `backend/requirements.txt`: add OpenCV/NumPy/OCR packages.
- Modify `backend/Dockerfile`: install Chinese/English Tesseract runtime data.
- Create `backend/test_line_art_extraction.py`: synthetic image, record, API, and DXF export regression tests.
- Modify `frontend/src/lib/renderApi.ts`: line-art response types and authenticated extraction APIs.
- Create `frontend/src/components/LineArtCropEditor.tsx`: original-image overlay with two draggable/resizable normalized crop boxes.
- Modify `frontend/src/app/render/page.tsx`: source switch, task picker, extraction previews, manual review, side selector, and unchanged final render submission.

### Task 1: Add Dependencies And The Unified Extraction Contract

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Modify: `backend/rendering/models.py`
- Modify: `backend/rendering/database.py`
- Create: `backend/test_line_art_extraction.py`

- [ ] **Step 1: Write the failing contract and record test**

Create `backend/test_line_art_extraction.py` with the repository path setup and this first test:

```python
import io
import os
import sys

import ezdxf
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))

from rendering.database import RenderDatabase
from rendering.models import CropBox, LineArtExtractionResponse, LineArtView


FAILURES = []


def check(name: str, condition: bool, detail=""):
    if condition:
        print(f"PASS: {name}")
    else:
        FAILURES.append(name)
        print(f"FAIL: {name}: {detail}")


def test_line_art_contract_and_record(tmp_dir):
    front = LineArtView(
        side="front",
        url="/api/render/files/temp/front.png",
        width=1200,
        height=2200,
        confidence=0.98,
        crop=CropBox(x=0.10, y=0.20, width=0.30, height=0.60),
    )
    response = LineArtExtractionResponse(
        id="extract-1",
        source="upload",
        originalUrl="/api/render/files/temp/source.png",
        front=front,
        back=None,
        needsReview=True,
        warnings=["未找到反面"],
    )
    check("response names missing side", response.warnings == ["未找到反面"], response.model_dump())

    db = RenderDatabase(base_dir=str(tmp_dir))
    saved = db.create_line_art_extraction(response.model_dump())
    loaded = db.get_line_art_extraction(saved["id"])
    check("extraction record round-trips", loaded["front"]["side"] == "front", loaded)
```

The test runner added at the end of this file must use a real temporary directory and exit non-zero on failure:

```python
if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_line_art_contract_and_record(tmp)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} line-art tests failed: {FAILURES}")
    print("All line-art tests passed")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python backend/test_line_art_extraction.py
```

Expected: import failure because the line-art models and extraction table do not exist.

- [ ] **Step 3: Add runtime dependencies**

Append pinned-compatible minimums to `backend/requirements.txt`:

```text
numpy>=2.0,<3
opencv-python-headless>=4.10,<5
pytesseract>=0.3.13,<1
matplotlib>=3.9,<4
```

Add these packages to the existing Debian `apt-get install` list in `backend/Dockerfile`:

```dockerfile
tesseract-ocr
tesseract-ocr-eng
tesseract-ocr-chi-sim
```

- [ ] **Step 4: Add exact Pydantic contracts**

Add to `backend/rendering/models.py`:

```python
class CropBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class LineArtView(BaseModel):
    side: Literal["front", "back"]
    url: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    crop: CropBox | None = None


class LineArtExtractionResponse(BaseModel):
    id: str
    source: Literal["task", "upload"]
    originalUrl: str = ""
    front: LineArtView | None = None
    back: LineArtView | None = None
    rotation: Literal[0, 90, 180, 270] = 0
    needsReview: bool = False
    warnings: list[str] = Field(default_factory=list)


class LineArtCropUpdate(BaseModel):
    front: CropBox
    back: CropBox
    rotation: Literal[0, 90, 180, 270] = 0
```

- [ ] **Step 5: Add a configurable extraction table**

Change `RenderDatabase.__init__` to accept an optional directory while preserving production defaults:

```python
class RenderDatabase:
    def __init__(self, base_dir: str = RENDER_DB_DIR):
        self.base_dir = base_dir
        self.model_configs = JsonTable(os.path.join(base_dir, "model_configs.json"), [])
        self.assets = JsonTable(os.path.join(base_dir, "assets.json"), [])
        self.tasks = JsonTable(os.path.join(base_dir, "tasks.json"), [])
        self.line_art_extractions = JsonTable(os.path.join(base_dir, "line_art_extractions.json"), [])
        self._ensure_default_config()
```

Add the following methods:

```python
def create_line_art_extraction(self, data: dict) -> dict:
    now = utc_now_iso()
    item = dict(data)
    item["id"] = item.get("id") or uuid.uuid4().hex[:12]
    item["createdAt"] = now
    item["updatedAt"] = now
    return self.line_art_extractions.update(lambda items: items.append(item) or item)

def get_line_art_extraction(self, extraction_id: str) -> dict | None:
    for item in self.line_art_extractions.load():
        if item.get("id") == extraction_id:
            return dict(item)
    return None

def update_line_art_extraction(self, extraction_id: str, patch: dict) -> dict | None:
    def mutate(items):
        for item in items:
            if item.get("id") == extraction_id:
                item.update(patch)
                item["updatedAt"] = utc_now_iso()
                return dict(item)
        return None
    return self.line_art_extractions.update(mutate)
```

- [ ] **Step 6: Run the contract test**

Run:

```bash
python backend/test_line_art_extraction.py
```

Expected: `All line-art tests passed`.

- [ ] **Step 7: Commit contracts and dependencies**

```bash
git add backend/requirements.txt backend/Dockerfile backend/rendering/models.py backend/rendering/database.py backend/test_line_art_extraction.py
git commit -m "Add line art extraction contracts"
```

### Task 2: Detect Front And Back Door Regions In Uploaded Sheets

**Files:**
- Create: `backend/rendering/line_art.py`
- Modify: `backend/test_line_art_extraction.py`

- [ ] **Step 1: Add a failing synthetic detection test**

Add this helper and test before the runner:

```python
from rendering.line_art import detect_order_sheet_views, extract_uploaded_sheet


def synthetic_order_sheet() -> bytes:
    image = Image.new("RGB", (1800, 1200), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 40, 1720, 180), outline="black", width=4)
    draw.rectangle((300, 300, 750, 1050), outline="black", width=8)
    draw.line((525, 300, 525, 1050), fill="black", width=5)
    draw.rectangle((1050, 300, 1500, 1050), outline="black", width=8)
    draw.line((1275, 300, 1275, 1050), fill="black", width=5)
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_upload_detector_finds_two_independent_views(tmp_dir):
    source = synthetic_order_sheet()
    boxes, warnings = detect_order_sheet_views(source)
    check("detector returns two boxes", len(boxes) == 2, boxes)
    check("front is left of back", boxes[0].x < boxes[1].x, boxes)
    result = extract_uploaded_sheet(source, "sheet.png", str(tmp_dir))
    check("front output exists", bool(result["front"]) and os.path.exists(result["front"]["filePath"]), result)
    check("back output exists", bool(result["back"]) and os.path.exists(result["back"]["filePath"]), result)
    check("outputs are separate files", result["front"]["filePath"] != result["back"]["filePath"], result)
```

Call the test from the temporary-directory runner.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python backend/test_line_art_extraction.py
```

Expected: FAIL because `rendering.line_art` does not exist.

- [ ] **Step 3: Implement normalized crop and candidate scoring**

Create `backend/rendering/line_art.py` with these concrete primitives:

```python
from __future__ import annotations

import io
import os
import uuid
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps

from .storage import public_file_url


@dataclass(frozen=True)
class NormalizedBox:
    x: float
    y: float
    width: float
    height: float

    def clamp(self) -> "NormalizedBox":
        x = min(max(self.x, 0.0), 0.99)
        y = min(max(self.y, 0.0), 0.99)
        width = min(max(self.width, 0.01), 1.0 - x)
        height = min(max(self.height, 0.01), 1.0 - y)
        return NormalizedBox(x, y, width, height)

    def pixels(self, image_width: int, image_height: int) -> tuple[int, int, int, int]:
        box = self.clamp()
        left = round(box.x * image_width)
        top = round(box.y * image_height)
        right = round((box.x + box.width) * image_width)
        bottom = round((box.y + box.height) * image_height)
        return left, top, max(left + 1, right), max(top + 1, bottom)


def _decode_original(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


def _analysis_image(image: Image.Image, max_side: int = 2400) -> tuple[np.ndarray, float]:
    ratio = min(1.0, max_side / max(image.size))
    size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    return cv2.cvtColor(np.asarray(resized), cv2.COLOR_RGB2BGR), ratio


def _rectangle_candidates(bgr: np.ndarray) -> list[tuple[float, tuple[int, int, int, int]]]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 41, 11)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    connected = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(connected, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_h, image_w = gray.shape
    image_area = image_w * image_h
    candidates = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area_ratio = (width * height) / image_area
        aspect = width / max(height, 1)
        if not (0.035 <= area_ratio <= 0.48 and 0.28 <= aspect <= 1.35 and height >= image_h * 0.25):
            continue
        rectangularity = cv2.contourArea(contour) / max(width * height, 1)
        vertical_bonus = min(height / max(width, 1), 3.0) / 3.0
        score = area_ratio * 3.0 + rectangularity + vertical_bonus
        candidates.append((score, (x, y, width, height)))
    candidates.sort(key=lambda item: item[0], reverse=True)
    deduped = []
    for score, box in candidates:
        x, y, width, height = box
        center = (x + width / 2, y + height / 2)
        if any(abs(center[0] - (bx + bw / 2)) < min(width, bw) * 0.35 and
               abs(center[1] - (by + bh / 2)) < min(height, bh) * 0.35
               for _other, (bx, by, bw, bh) in deduped):
            continue
        deduped.append((score, box))
        if len(deduped) == 8:
            break
    return deduped
```

- [ ] **Step 4: Add OCR anchors and deterministic left/right fallback**

Add these functions to the same file:

```python
def _ocr_anchor_x(bgr: np.ndarray) -> dict[str, float]:
    anchors = {}
    try:
        data = pytesseract.image_to_data(bgr, lang="chi_sim+eng", output_type=pytesseract.Output.DICT,
                                         config="--psm 11")
    except Exception:
        return anchors
    for index, raw in enumerate(data.get("text", [])):
        text = str(raw or "").replace(" ", "")
        for label, side in (("正面", "front"), ("背面", "back"), ("反面", "back")):
            if label in text:
                anchors[side] = float(data["left"][index] + data["width"][index] / 2)
    return anchors


def detect_order_sheet_views(data: bytes) -> tuple[list[NormalizedBox], list[str]]:
    image = _decode_original(data)
    bgr, ratio = _analysis_image(image)
    candidates = _rectangle_candidates(bgr)
    warnings = []
    if len(candidates) < 2:
        return [], ["未检测到两个独立门体区域，请手动框选正面和反面"]
    anchors = _ocr_anchor_x(bgr)
    selected = candidates[:2]
    if anchors.get("front") is not None and anchors.get("back") is not None:
        available = list(candidates)
        ordered = []
        for side in ("front", "back"):
            match = min(available, key=lambda item: abs(item[1][0] + item[1][2] / 2 - anchors[side]))
            ordered.append(match)
            available.remove(match)
        selected = ordered
    else:
        selected = sorted(selected, key=lambda item: item[1][0])
        warnings.append("未识别到完整正反面文字锚点，已按左正面、右反面排序，请确认")
    boxes = []
    analysis_h, analysis_w = bgr.shape[:2]
    for _score, (x, y, width, height) in selected:
        pad_x = max(4, round(width * 0.02))
        pad_y = max(4, round(height * 0.02))
        left = max(0, x - pad_x)
        top = max(0, y - pad_y)
        right = min(analysis_w, x + width + pad_x)
        bottom = min(analysis_h, y + height + pad_y)
        boxes.append(NormalizedBox(left / analysis_w, top / analysis_h,
                                   (right - left) / analysis_w, (bottom - top) / analysis_h))
    return boxes, warnings
```

- [ ] **Step 5: Save original-quality source and lossless line-art crops**

Add:

```python
def _save_png(image: Image.Image, folder: str, stem: str) -> dict:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{stem}-{uuid.uuid4().hex}.png")
    image.save(path, "PNG", optimize=False)
    return {
        "filePath": path,
        "url": public_file_url(path),
        "width": image.width,
        "height": image.height,
    }


def _line_art_crop(image: Image.Image, box: NormalizedBox) -> Image.Image:
    crop = image.crop(box.pixels(image.width, image.height))
    gray = np.asarray(crop.convert("L"))
    cleaned = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 41, 9)
    return Image.fromarray(cleaned, mode="L")


def extract_uploaded_sheet(data: bytes, filename: str, output_dir: str) -> dict:
    image = _decode_original(data)
    original = _save_png(image, output_dir, "order-sheet-original")
    boxes, warnings = detect_order_sheet_views(data)
    if len(boxes) != 2:
        boxes = [
            NormalizedBox(0.08, 0.18, 0.40, 0.72),
            NormalizedBox(0.52, 0.18, 0.40, 0.72),
        ]
        if "已提供可调整的默认正反面范围" not in warnings:
            warnings.append("已提供可调整的默认正反面范围")
    sides = ["front", "back"]
    result = {
        "source": "upload",
        "originalUrl": original["url"],
        "originalPath": original["filePath"],
        "sourcePath": original["filePath"],
        "front": None,
        "back": None,
        "rotation": 0,
        "needsReview": bool(warnings),
        "warnings": warnings,
    }
    for side, box in zip(sides, boxes):
        saved = _save_png(_line_art_crop(image, box), output_dir, f"line-art-{side}")
        result[side] = {
            **saved,
            "side": side,
            "confidence": 0.92 if not warnings else 0.72,
            "crop": box.__dict__,
        }
    return result
```

Use the existing render `TEMP_DIR` when production callers invoke this function. The original is always re-encoded losslessly as PNG; no thumbnail is used for extraction.

- [ ] **Step 6: Run the synthetic detector test**

Run:

```bash
python backend/test_line_art_extraction.py
```

Expected: both independent output files exist; the front crop is left of the back crop.

- [ ] **Step 7: Commit upload detection**

```bash
git add backend/rendering/line_art.py backend/test_line_art_extraction.py
git commit -m "Extract front and back line art from uploads"
```

### Task 3: Add Authenticated Upload, Read, And Manual Recrop APIs

**Files:**
- Modify: `backend/rendering/line_art.py`
- Modify: `backend/rendering/routes.py`
- Modify: `backend/test_line_art_extraction.py`

- [ ] **Step 1: Add a failing manual-recrop test**

Add:

```python
from rendering.line_art import recrop_extraction


def test_manual_recrop_replaces_both_views(tmp_dir):
    result = extract_uploaded_sheet(synthetic_order_sheet(), "sheet.png", str(tmp_dir))
    record = {"id": "manual-1", **result}
    front_box = {"x": 0.15, "y": 0.20, "width": 0.30, "height": 0.68}
    back_box = {"x": 0.55, "y": 0.20, "width": 0.30, "height": 0.68}
    updated = recrop_extraction(record, front_box, back_box, 0, str(tmp_dir))
    check("manual crop clears review flag", updated["needsReview"] is False, updated)
    check("manual front crop persisted", updated["front"]["crop"] == front_box, updated["front"])
    check("manual back crop persisted", updated["back"]["crop"] == back_box, updated["back"])
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python backend/test_line_art_extraction.py
```

Expected: FAIL because `recrop_extraction` is undefined.

- [ ] **Step 3: Implement recropping from the stored original**

Add to `backend/rendering/line_art.py`:

```python
def recrop_extraction(record: dict, front: dict, back: dict, rotation: int, output_dir: str) -> dict:
    original_path = record.get("sourcePath") or record.get("originalPath", "")
    if not original_path or not os.path.isfile(original_path):
        raise FileNotFoundError("原始订货单文件不存在，无法重新裁剪")
    with Image.open(original_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    transpose = {
        0: None,
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }.get(rotation)
    if transpose is None and rotation != 0:
        raise ValueError("旋转角度只支持 0、90、180、270")
    if transpose is not None:
        image = image.transpose(transpose)
    updated = dict(record)
    preview = _save_png(image, output_dir, "order-sheet-rotated")
    updated["originalUrl"] = preview["url"]
    updated["originalPath"] = preview["filePath"]
    updated["rotation"] = rotation
    for side, raw_box in (("front", front), ("back", back)):
        box = NormalizedBox(**raw_box).clamp()
        saved = _save_png(_line_art_crop(image, box), output_dir, f"line-art-{side}")
        updated[side] = {
            **saved,
            "side": side,
            "confidence": 1.0,
            "crop": box.__dict__,
        }
    updated["needsReview"] = False
    updated["warnings"] = []
    return updated
```

- [ ] **Step 4: Add the authenticated routes**

Extend imports in `backend/rendering/routes.py` with `LineArtCropUpdate`, `LineArtExtractionResponse`, `extract_uploaded_sheet`, `recrop_extraction`, and `TEMP_DIR`. Add:

```python
@render_router.post("/api/render/line-art/extract/upload", response_model=LineArtExtractionResponse)
async def extract_line_art_upload(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    content_type = (file.content_type or "").lower()
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="只支持 PNG、JPG、JPEG、WEBP 图片")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传图片为空")
    try:
        payload = extract_uploaded_sheet(data, file.filename or "order-sheet.png", TEMP_DIR)
    except Exception as exc:
        logger.exception("Line-art upload extraction failed")
        raise HTTPException(status_code=422, detail=f"线稿提取失败: {type(exc).__name__}: {exc}") from exc
    saved = render_db.create_line_art_extraction(payload)
    return LineArtExtractionResponse.model_validate(saved)


@render_router.get("/api/render/line-art/extractions/{extraction_id}", response_model=LineArtExtractionResponse)
def get_line_art_extraction(extraction_id: str, current_user: dict = Depends(get_current_user)):
    record = render_db.get_line_art_extraction(extraction_id)
    if not record:
        raise HTTPException(status_code=404, detail="线稿提取记录不存在")
    return LineArtExtractionResponse.model_validate(record)


@render_router.put("/api/render/line-art/extractions/{extraction_id}/crop", response_model=LineArtExtractionResponse)
def update_line_art_crop(
    extraction_id: str,
    data: LineArtCropUpdate,
    current_user: dict = Depends(get_current_user),
):
    record = render_db.get_line_art_extraction(extraction_id)
    if not record:
        raise HTTPException(status_code=404, detail="线稿提取记录不存在")
    try:
        updated = recrop_extraction(
            record,
            data.front.model_dump(),
            data.back.model_dump(),
            data.rotation,
            TEMP_DIR,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved = render_db.update_line_art_extraction(extraction_id, updated)
    return LineArtExtractionResponse.model_validate(saved)
```

- [ ] **Step 5: Add authentication and malformed-crop API assertions**

Add these imports and concrete tests. They use FastAPI dependency overrides and restore the production database object in `finally`:

```python
from fastapi.testclient import TestClient

from auth import get_current_user
from main import app
from rendering import routes as render_routes_module


def test_upload_route_requires_login():
    app.dependency_overrides.clear()
    client = TestClient(app)
    response = client.post(
        "/api/render/line-art/extract/upload",
        files={"file": ("sheet.png", synthetic_order_sheet(), "image/png")},
    )
    check("line-art upload requires login", response.status_code == 401, response.text)


def test_crop_route_rejects_missing_record(tmp_dir):
    original_db = render_routes_module.render_db
    render_routes_module.render_db = RenderDatabase(base_dir=str(tmp_dir))
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "line-art-test",
        "name": "线稿测试",
        "role": "绘图员",
        "default_module": "效果渲染",
    }
    try:
        client = TestClient(app)
        response = client.put(
            "/api/render/line-art/extractions/missing/crop",
            json={
                "front": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.7},
                "back": {"x": 0.6, "y": 0.1, "width": 0.3, "height": 0.7},
            },
        )
        check("missing extraction is 404", response.status_code == 404, response.text)
    finally:
        app.dependency_overrides.clear()
        render_routes_module.render_db = original_db
```

Call `test_upload_route_requires_login()` and `test_crop_route_rejects_missing_record(tmp)` from the existing temporary-directory runner. No production password is used.

- [ ] **Step 6: Run tests**

Run:

```bash
python backend/test_line_art_extraction.py
python backend/test_security_phase1.py
```

Expected: line-art tests and all existing authentication tests PASS.

- [ ] **Step 7: Commit upload APIs**

```bash
git add backend/rendering/line_art.py backend/rendering/routes.py backend/test_line_art_extraction.py
git commit -m "Add authenticated line art extraction APIs"
```

### Task 4: Export Clean Front And Back PNGs From A Linked CAD Task

**Files:**
- Create: `backend/rendering/cad_line_art.py`
- Modify: `backend/main.py`
- Modify: `backend/test_line_art_extraction.py`

- [ ] **Step 1: Add a failing deterministic DXF export test**

Build a small DXF with titles, door geometry, and dimensions:

```python
from rendering.cad_line_art import export_dxf_line_art


def sample_front_back_dxf() -> str:
    doc = ezdxf.new("R2010")
    doc.layers.add("A-DOOR-PANEL")
    doc.layers.add("YQ_DIM")
    ms = doc.modelspace()
    ms.add_text("正面", dxfattribs={"height": 80}).set_placement((500, 2400))
    ms.add_lwpolyline([(0, 0), (1000, 0), (1000, 2200), (0, 2200)], close=True,
                      dxfattribs={"layer": "A-DOOR-PANEL"})
    ms.add_line((-200, -200), (1200, -200), dxfattribs={"layer": "YQ_DIM"})
    ms.add_text("背面", dxfattribs={"height": 80}).set_placement((2500, 2400))
    ms.add_lwpolyline([(2000, 0), (3000, 0), (3000, 2200), (2000, 2200)], close=True,
                      dxfattribs={"layer": "A-DOOR-PANEL"})
    output = io.StringIO()
    doc.write(output)
    return output.getvalue()


def test_dxf_export_returns_two_clean_pngs(tmp_dir):
    result = export_dxf_line_art(sample_front_back_dxf(), str(tmp_dir))
    check("DXF front PNG exists", os.path.isfile(result["front"]["filePath"]), result)
    check("DXF back PNG exists", os.path.isfile(result["back"]["filePath"]), result)
    with Image.open(result["front"]["filePath"]) as image:
        check("DXF PNG is high resolution", max(image.size) >= 2000, image.size)
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
python backend/test_line_art_extraction.py
```

Expected: FAIL because `rendering.cad_line_art` does not exist.

- [ ] **Step 3: Implement DXF view discovery and layer filtering**

Create `backend/rendering/cad_line_art.py`. Use ezdxf bounding boxes for top-level entity selection so INSERT blocks and HATCH entities remain renderable:

```python
from __future__ import annotations

import io
import os
import uuid

import ezdxf
from ezdxf import bbox
from ezdxf.addons.drawing.matplotlib import qsave
from PIL import Image

from .storage import public_file_url


EXCLUDED_LAYERS = {"YQ_DIM", "A-DOOR-mark", "Defpoints"}
EXCLUDED_TYPES = {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MLEADER"}


def _plain_text(entity) -> str:
    if entity.dxftype() == "TEXT":
        return str(entity.dxf.text or "").strip()
    if entity.dxftype() == "MTEXT":
        return str(entity.plain_text() or "").strip()
    return ""


def _title_anchors(modelspace) -> dict[str, float]:
    anchors = {}
    for entity in modelspace.query("TEXT MTEXT"):
        text = _plain_text(entity)
        insert = entity.dxf.insert
        if text == "正面":
            anchors["front"] = float(insert.x)
        elif text in {"背面", "反面"}:
            anchors["back"] = float(insert.x)
    if "front" not in anchors or "back" not in anchors:
        raise ValueError("DXF 中未找到正面和背面标题锚点")
    return anchors


def _view_filter(modelspace, side: str):
    anchors = _title_anchors(modelspace)
    own_x = anchors[side]
    other_x = anchors["back" if side == "front" else "front"]
    half_gap = max(abs(other_x - own_x) * 0.46, 1200.0)

    def accepts(entity) -> bool:
        if entity.dxftype() in EXCLUDED_TYPES:
            return False
        if str(entity.dxf.layer or "0") in EXCLUDED_LAYERS:
            return False
        bounds = bbox.extents([entity], fast=True)
        if not bounds.has_data:
            return False
        return abs(float(bounds.center.x) - own_x) <= half_gap

    return accepts
```

- [ ] **Step 4: Render each view with ezdxf's drawing backend**

Add to the same file:

```python
def export_dxf_line_art(dxf_text: str, output_dir: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    doc = ezdxf.read(io.StringIO(dxf_text))
    modelspace = doc.modelspace()
    result = {"source": "task", "originalUrl": "", "needsReview": False, "warnings": []}
    for side in ("front", "back"):
        path = os.path.join(output_dir, f"cad-line-art-{side}-{uuid.uuid4().hex}.png")
        qsave(
            modelspace,
            path,
            bg="#FFFFFFFF",
            fg="#000000FF",
            dpi=300,
            backend="agg",
            filter_func=_view_filter(modelspace, side),
            size_inches=(0.0, 8.0),
        )
        with Image.open(path) as image:
            width, height = image.size
        if max(width, height) < 2000:
            raise ValueError(f"{side}线稿分辨率不足: {width}x{height}")
        result[side] = {
            "side": side,
            "filePath": path,
            "url": public_file_url(path),
            "width": width,
            "height": height,
            "confidence": 1.0,
            "crop": None,
        }
    return result
```

This path preserves HATCH rendering, INSERT contents, arcs, circles, existing hardware masks, and optional `A-DOOR-OCCLUSION` WIPEOUTs. It filters all text, dimensions, leaders, mark layers, and dimension layers before rasterization.

- [ ] **Step 5: Add the task-linked endpoint in `backend/main.py`**

Import `export_dxf_line_art`, `render_db`, `LineArtExtractionResponse`, and render `TEMP_DIR`. Add the route beside the CAD endpoints so it can safely access `task_db` and `_cached_cad`:

```python
@app.post(
    "/api/render/line-art/extract/task/{task_id}",
    response_model=LineArtExtractionResponse,
)
def extract_line_art_from_task(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    task = task_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="关联图纸项目不存在")
    try:
        req = CADRequest.model_validate(task.get("params") or {})
        _cache_key, dxf_bytes, _cache_hit = _cached_cad(req)
        if not dxf_bytes:
            raise ValueError("关联项目无法生成 DXF")
        payload = export_dxf_line_art(dxf_bytes.decode("utf-8"), TEMP_DIR)
    except Exception as exc:
        logger.exception("Task line-art export failed: task_id=%s", task_id)
        raise HTTPException(status_code=422, detail=f"关联项目线稿导出失败: {type(exc).__name__}: {exc}") from exc
    saved = render_db.create_line_art_extraction(payload)
    return LineArtExtractionResponse.model_validate(saved)
```

Do not call the public HTTP endpoint from the backend; this route reuses the same cached DXF bytes as `generate_cad_preview`.

- [ ] **Step 6: Run DXF and existing CAD tests**

Run:

```bash
python backend/test_line_art_extraction.py
python backend/test_cad_new_options.py
```

Expected: two high-resolution PNGs are produced and existing CAD generation remains unchanged.

- [ ] **Step 7: Commit linked-project export**

```bash
git add backend/rendering/cad_line_art.py backend/main.py backend/test_line_art_extraction.py
git commit -m "Export linked CAD tasks as front and back line art"
```

### Task 5: Add Frontend Types And Authenticated Line-Art APIs

**Files:**
- Modify: `frontend/src/lib/renderApi.ts`

- [ ] **Step 1: Add response types**

Add:

```ts
export type LineArtSide = "front" | "back";

export interface CropBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ExtractedLineArtView {
  side: LineArtSide;
  url: string;
  width: number;
  height: number;
  confidence: number;
  crop: CropBox | null;
}

export interface LineArtExtraction {
  id: string;
  source: "task" | "upload";
  originalUrl: string;
  front: ExtractedLineArtView | null;
  back: ExtractedLineArtView | null;
  rotation: 0 | 90 | 180 | 270;
  needsReview: boolean;
  warnings: string[];
}
```

- [ ] **Step 2: Add API functions using the existing authenticated client**

Add:

```ts
export async function extractLineArtFromTask(taskId: string): Promise<LineArtExtraction> {
  const response = await api.post<LineArtExtraction>(`/render/line-art/extract/task/${encodeURIComponent(taskId)}`);
  return response.data;
}

export async function extractLineArtFromUpload(file: File): Promise<LineArtExtraction> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post<LineArtExtraction>("/render/line-art/extract/upload", formData, { timeout: 120000 });
  return response.data;
}

export async function updateLineArtCrop(
  extractionId: string,
  front: CropBox,
  back: CropBox,
  rotation: 0 | 90 | 180 | 270,
): Promise<LineArtExtraction> {
  const response = await api.put<LineArtExtraction>(
    `/render/line-art/extractions/${encodeURIComponent(extractionId)}/crop`,
    { front, back, rotation },
  );
  return response.data;
}

export async function authenticatedImageFile(url: string, filename: string): Promise<File> {
  const apiPath = url.startsWith("/api/") ? url.slice(4) : url;
  const response = await api.get<Blob>(apiPath, { responseType: "blob", timeout: 120000 });
  const contentType = response.headers["content-type"] || "image/png";
  return new File([response.data], filename, { type: contentType });
}
```

Use the existing `api` instance already imported by this module. This preserves authentication for protected `/api/render/files/...` URLs and avoids exposing a direct public file URL.

- [ ] **Step 3: Run TypeScript checks**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: PASS with no unused types or invalid Axios generics.

- [ ] **Step 4: Commit frontend APIs**

```bash
git add frontend/src/lib/renderApi.ts
git commit -m "Add frontend line art extraction APIs"
```

### Task 6: Build The Two-Box Manual Crop Editor

**Files:**
- Create: `frontend/src/components/LineArtCropEditor.tsx`
- Modify: `frontend/src/app/render/page.tsx`

- [ ] **Step 1: Create a controlled crop editor with pointer events**

Create `frontend/src/components/LineArtCropEditor.tsx` with this public contract:

```tsx
"use client";

import { useRef, useState } from "react";
import type { CropBox, LineArtSide } from "@/lib/renderApi";

type Props = {
  imageUrl: string;
  front: CropBox;
  back: CropBox;
  onChange: (side: LineArtSide, box: CropBox) => void;
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export default function LineArtCropEditor({ imageUrl, front, back, onChange }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<{
    side: LineArtSide;
    mode: "move" | "resize";
    startX: number;
    startY: number;
    initial: CropBox;
  } | null>(null);

  function start(side: LineArtSide, mode: "move" | "resize", event: React.PointerEvent) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const box = side === "front" ? front : back;
    setDrag({ side, mode, startX: event.clientX, startY: event.clientY, initial: box });
  }

  function move(event: React.PointerEvent) {
    if (!drag || !rootRef.current) return;
    const rect = rootRef.current.getBoundingClientRect();
    const dx = (event.clientX - drag.startX) / rect.width;
    const dy = (event.clientY - drag.startY) / rect.height;
    if (drag.mode === "move") {
      onChange(drag.side, {
        ...drag.initial,
        x: clamp(drag.initial.x + dx, 0, 1 - drag.initial.width),
        y: clamp(drag.initial.y + dy, 0, 1 - drag.initial.height),
      });
      return;
    }
    onChange(drag.side, {
      ...drag.initial,
      width: clamp(drag.initial.width + dx, 0.05, 1 - drag.initial.x),
      height: clamp(drag.initial.height + dy, 0.05, 1 - drag.initial.y),
    });
  }

  const boxes: Array<[LineArtSide, CropBox, string]> = [
    ["front", front, "正面"],
    ["back", back, "反面"],
  ];

  return (
    <div className="flex max-h-[72vh] justify-center overflow-auto bg-white">
      <div
        ref={rootRef}
        className="relative inline-block touch-none"
        onPointerMove={move}
        onPointerUp={() => setDrag(null)}
        onPointerCancel={() => setDrag(null)}
      >
        <img src={imageUrl} alt="订货单原图" className="block max-h-[72vh] max-w-full" draggable={false} />
        {boxes.map(([side, box, label]) => (
          <div
            key={side}
            className={`absolute border-2 ${side === "front" ? "border-[#007AFF]" : "border-[#ef4444]"}`}
            style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }}
            onPointerDown={(event) => start(side, "move", event)}
          >
            <span className="absolute left-0 top-0 bg-black/70 px-1.5 py-0.5 text-xs text-white">{label}</span>
            <button
              type="button"
              aria-label={`调整${label}裁剪框大小`}
              className="absolute bottom-0 right-0 h-5 w-5 translate-x-1/2 translate-y-1/2 cursor-nwse-resize border border-white bg-[#007AFF]"
              onPointerDown={(event) => { event.stopPropagation(); start(side, "resize", event); }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add crop-dialog state to the render page**

Add state:

```tsx
const [cropEditorOpen, setCropEditorOpen] = useState(false);
const [cropDraft, setCropDraft] = useState<{ front: CropBox; back: CropBox; rotation: 0 | 90 | 180 | 270 } | null>(null);
```

Add one local error helper used by all new extraction actions:

```tsx
function lineArtErrorMessage(error: unknown): string {
  const value = error as { userMessage?: string; message?: string };
  return value.userMessage || value.message || "线稿处理失败";
}
```

When an upload extraction contains crops, initialize it exactly once:

```tsx
function openCropEditor(extraction: LineArtExtraction) {
  if (!extraction.front?.crop || !extraction.back?.crop) {
    setMessage("当前结果缺少正面或反面裁剪框，请重新上传清晰订货单");
    return;
  }
  setCropDraft({ front: extraction.front.crop, back: extraction.back.crop, rotation: extraction.rotation });
  setCropEditorOpen(true);
}
```

Save with:

```tsx
async function confirmCrop() {
  if (!lineArtExtraction || !cropDraft) return;
  setLineArtBusy(true);
  try {
    const updated = await updateLineArtCrop(
      lineArtExtraction.id,
      cropDraft.front,
      cropDraft.back,
      cropDraft.rotation,
    );
    setLineArtExtraction(updated);
    setCropEditorOpen(false);
    setMessage("正反面线稿已按新范围重新提取");
  } catch (error: unknown) {
    setErrorDialog({ title: "线稿裁剪失败", message: lineArtErrorMessage(error) });
  } finally {
    setLineArtBusy(false);
  }
}
```

Add a rotation action that always starts from the immutable source image, resets to two editable default boxes, and immediately refreshes the preview:

```tsx
async function rotateCrop(delta: 90 | -90) {
  if (!lineArtExtraction || !cropDraft) return;
  const rotation = ((cropDraft.rotation + delta + 360) % 360) as 0 | 90 | 180 | 270;
  const front = { x: 0.08, y: 0.18, width: 0.40, height: 0.72 };
  const back = { x: 0.52, y: 0.18, width: 0.40, height: 0.72 };
  setLineArtBusy(true);
  try {
    const updated = await updateLineArtCrop(lineArtExtraction.id, front, back, rotation);
    setLineArtExtraction(updated);
    setCropDraft({
      front: updated.front?.crop || front,
      back: updated.back?.crop || back,
      rotation: updated.rotation,
    });
  } catch (error: unknown) {
    setErrorDialog({ title: "线稿旋转失败", message: lineArtErrorMessage(error) });
  } finally {
    setLineArtBusy(false);
  }
}
```

- [ ] **Step 3: Render the modal with blank-area and close-button dismissal**

Add this modal near the existing image preview modal:

```tsx
{cropEditorOpen && cropDraft && lineArtExtraction?.originalUrl && (
  <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/55 p-5" onClick={() => setCropEditorOpen(false)}>
    <div className="max-h-[92vh] w-full max-w-6xl overflow-auto bg-white p-4" onClick={(event) => event.stopPropagation()}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[16px] font-semibold">调整正反面裁剪范围</h3>
        <button type="button" aria-label="关闭裁剪" className="h-8 w-8 text-[22px]" onClick={() => setCropEditorOpen(false)}>×</button>
      </div>
      <LineArtCropEditor
        imageUrl={lineArtExtraction.originalUrl}
        front={cropDraft.front}
        back={cropDraft.back}
        onChange={(side, box) => setCropDraft((current) => current ? { ...current, [side]: box } : current)}
      />
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" className="rounded-lg px-3 py-2" disabled={lineArtBusy} onClick={() => void rotateCrop(-90)}>左转90°</button>
        <button type="button" className="rounded-lg px-3 py-2" disabled={lineArtBusy} onClick={() => void rotateCrop(90)}>右转90°</button>
        <button type="button" className="rounded-lg px-3 py-2" onClick={() => openCropEditor(lineArtExtraction)}>重置识别框</button>
        <button type="button" className="rounded-lg px-4 py-2" onClick={() => setCropEditorOpen(false)}>取消</button>
        <button type="button" className="rounded-lg bg-[#007AFF] px-4 py-2 text-white" disabled={lineArtBusy} onClick={confirmCrop}>保存并重新提取</button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 4: Run frontend checks**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: the component compiles, pointer event types are valid, and no accessibility lint errors are introduced.

- [ ] **Step 5: Commit the crop editor**

```bash
git add frontend/src/components/LineArtCropEditor.tsx frontend/src/app/render/page.tsx
git commit -m "Add manual front and back crop editor"
```

### Task 7: Integrate Both Sources, Two Previews, And Single-Side Submission

**Files:**
- Modify: `frontend/src/app/render/page.tsx`
- Modify: `frontend/src/lib/renderApi.ts`

- [ ] **Step 1: Add exact source and selection state**

Import `TaskProjectCombobox`, `getTasks`, the line-art API functions/types, and the crop editor. Add:

```tsx
type LineArtSourceMode = "task" | "upload" | "direct";

const [lineArtSource, setLineArtSource] = useState<LineArtSourceMode>("task");
const [drawingTasks, setDrawingTasks] = useState<TaskItem[]>([]);
const [selectedDrawingTaskId, setSelectedDrawingTaskId] = useState("");
const [orderSheetFile, setOrderSheetFile] = useState<File | null>(null);
const [lineArtExtraction, setLineArtExtraction] = useState<LineArtExtraction | null>(null);
const [selectedLineArtSide, setSelectedLineArtSide] = useState<LineArtSide>("front");
const [lineArtBusy, setLineArtBusy] = useState(false);
```

Load drawing tasks separately from render history so switching render source does not refetch model configurations:

```tsx
useEffect(() => {
  void getTasks({ limit: 200 }).then((response) => setDrawingTasks(response.tasks));
}, []);
```

- [ ] **Step 2: Add source actions**

```tsx
async function extractFromSelectedTask() {
  if (!selectedDrawingTaskId) return setMessage("请选择关联图纸项目");
  setLineArtBusy(true);
  try {
    const result = await extractLineArtFromTask(selectedDrawingTaskId);
    setLineArtExtraction(result);
    setSelectedLineArtSide(result.front ? "front" : "back");
    setMessage("已生成正面和反面两张独立线稿");
  } catch (error: unknown) {
    setErrorDialog({ title: "关联项目线稿生成失败", message: lineArtErrorMessage(error) });
  } finally {
    setLineArtBusy(false);
  }
}

async function extractFromOrderSheet() {
  if (!orderSheetFile) return setMessage("请上传整张订货单");
  setLineArtBusy(true);
  try {
    const result = await extractLineArtFromUpload(orderSheetFile);
    setLineArtExtraction(result);
    setSelectedLineArtSide(result.front ? "front" : "back");
    setMessage(result.needsReview ? "已自动提取，请确认或调整正反面范围" : "正反面线稿提取完成");
  } catch (error: unknown) {
    setErrorDialog({ title: "订货单线稿提取失败", message: lineArtErrorMessage(error) });
  } finally {
    setLineArtBusy(false);
  }
}
```

`direct` mode continues to use the existing `UploadBox` and `lineArt: File | null` state for users who already have a clean single-side line art image.

- [ ] **Step 3: Replace the single line-art box with a compact source panel**

Use a three-option segmented control labeled only by its values:

```tsx
const activeSegmentClass = "rounded-lg bg-[#007AFF] px-3 py-2 text-[13px] text-white";
const segmentClass = "rounded-lg bg-[#F2F2F7] px-3 py-2 text-[13px] text-[#1C1C1E]";

{(["task", "upload", "direct"] as LineArtSourceMode[]).map((mode) => (
  <button
    type="button"
    key={mode}
    className={lineArtSource === mode ? activeSegmentClass : segmentClass}
    onClick={() => setLineArtSource(mode)}
  >
    {{ task: "关联项目图纸", upload: "上传整张订货单", direct: "直接上传线稿" }[mode]}
  </button>
))}
```

For task mode render `<TaskProjectCombobox tasks={drawingTasks} value={selectedDrawingTaskId} onChange={setSelectedDrawingTaskId} />` plus a button with `onClick={extractFromSelectedTask}`. For upload mode render `<UploadBox title="整张订货单" file={orderSheetFile} onPick={setOrderSheetFile} onPreview={(src, title) => setPreviewImage({ src, title })} required />` plus a button with `onClick={extractFromOrderSheet}`. Render the existing reference style `UploadBox` immediately after the source panel.

- [ ] **Step 4: Render two independent result cards with one selected side**

```tsx
{lineArtExtraction && (
  <div className="grid gap-3 md:grid-cols-2">
    {(["front", "back"] as LineArtSide[]).map((side) => {
      const view = lineArtExtraction[side];
      const label = side === "front" ? "正面线稿" : "反面线稿";
      return (
        <label key={side} className={`border p-3 ${selectedLineArtSide === side ? "border-[#007AFF]" : "border-[#e5e7eb]"}`}>
          <div className="mb-2 flex items-center justify-between">
            <span className="font-medium">{label}</span>
            <input type="radio" name="line-art-side" checked={selectedLineArtSide === side}
                   disabled={!view} onChange={() => setSelectedLineArtSide(side)} />
          </div>
          {view ? (
            <button type="button" className="block w-full" onClick={() => setPreviewImage({ src: view.url, title: label })}>
              <img src={view.url} alt={label} className="h-56 w-full object-contain" />
            </button>
          ) : (
            <div className="flex h-56 items-center justify-center bg-[#f8fafc] text-[#ef4444]">未提取到{label}</div>
          )}
        </label>
      );
    })}
  </div>
)}
```

Render review feedback directly below the two cards and disable the final command while an extracted result still needs confirmation:

```tsx
{lineArtExtraction.needsReview && (
  <div className="mt-3 flex items-start justify-between gap-3 bg-[#fff7ed] p-3 text-[12px] text-[#9a3412]">
    <div>{lineArtExtraction.warnings.length ? lineArtExtraction.warnings.join("；") : "请确认正反面裁剪范围"}</div>
    {lineArtExtraction.source === "upload" && (
      <button type="button" className="shrink-0 font-medium text-[#007AFF]" onClick={() => openCropEditor(lineArtExtraction)}>
        调整裁剪范围
      </button>
    )}
  </div>
)}
```

Set the existing submit button's `disabled` value to:

```tsx
disabled={loading || lineArtBusy || (lineArtSource !== "direct" && Boolean(lineArtExtraction?.needsReview))}
```

- [ ] **Step 5: Resolve exactly one line-art file before calling the existing render API**

Add:

```tsx
async function resolveSelectedLineArt(): Promise<File | null> {
  if (lineArtSource === "direct") return lineArt;
  if (!lineArtExtraction || lineArtExtraction.needsReview) return null;
  const selected = lineArtExtraction[selectedLineArtSide];
  if (!selected) return null;
  return authenticatedImageFile(selected.url, `${selectedLineArtSide}-line-art.png`);
}
```

At the start of `submitTask`, replace the direct `lineArt` check with:

```tsx
const selectedLineArt = await resolveSelectedLineArt();
if (!selectedLineArt) {
  setMessage(lineArtExtraction?.needsReview ? "请先确认正反面裁剪范围" : "请选择可用的正面或反面线稿");
  return;
}
```

Pass only this file into the unchanged call:

```tsx
createRenderTask({
  modelConfigId: saved.id,
  prompt: buildRenderPrompt(prompt, referencePromptGuidance),
  size,
  count: 1,
  selectedAssetIds: taskAssetIds,
  lineArt: selectedLineArt,
  styleReference,
  tempAssets: taskTempAssets,
})
```

Do not add `front`, `back`, `extractionId`, or source-specific fields to `/api/render/tasks`; this is the regression guard that keeps Provider behavior unchanged.

- [ ] **Step 6: Verify source switching and submission manually**

Start the local stack and verify:

```bash
docker compose up -d --build backend frontend
```

Acceptance sequence:

1. Link a drawing project and receive two separate previews without dimensions or titles.
2. Select front, submit, and inspect the multipart request: exactly one `lineArt` file is present.
3. Select back and submit again: the back PNG is the only `lineArt` file.
4. Upload the provided order-sheet sample, adjust both boxes, save, and verify `needsReview` clears.
5. Click either preview to enlarge, then close by the X button and by clicking the backdrop.
6. Switch to direct upload and submit an existing clean PNG without running extraction.

- [ ] **Step 7: Run all automated checks**

Run:

```bash
python backend/test_line_art_extraction.py
python backend/test_render_background_task.py
python backend/test_cad_new_options.py
python backend/test_security_phase1.py
cd frontend && npm run lint && npm run build
```

Expected: all backend scripts report zero failures; frontend lint and build PASS.

- [ ] **Step 8: Commit the integrated workflow**

```bash
git add frontend/src/app/render/page.tsx frontend/src/lib/renderApi.ts
git commit -m "Add dual-channel front and back line art workflow"
```

### Task 8: Production And Visual Verification

**Files:**
- Verify only; change tests only when a reproducible regression is discovered.

- [ ] **Step 1: Build the production containers**

Run:

```bash
docker compose build backend frontend
```

Expected: OpenCV imports successfully, `tesseract --list-langs` includes `chi_sim` and `eng`, and the frontend production build succeeds.

- [ ] **Step 2: Verify protected file access**

With no session, request an extracted image URL and expect `401`. Log in through the frontend and verify the same URL loads in previews and through `authenticatedImageFile`.

- [ ] **Step 3: Verify source quality**

For the provided order-sheet sample and one system-linked CAD task, inspect the generated PNG dimensions and pixels:

- longest side is at least 2000 px;
- PNG is lossless and no JPEG thumbnail is substituted;
- title block, dimensions, order table, and remarks are outside the selected output;
- door panel, frame, trim, hatches, handles, locks, and hinges remain visible;
- front and back are two different files and are not merged.

- [ ] **Step 4: Verify failure feedback**

Upload one blurry image and one image containing only a single door. Confirm the response names the missing side, sets `needsReview=true`, keeps the original image available, and lets the user manually draw both crop boxes without losing reference assets or model configuration state.

- [ ] **Step 5: Commit verification-only fixes if needed**

```bash
git add backend/test_line_art_extraction.py
git commit -m "Verify dual-channel line art extraction"
```

Skip this commit when verification requires no test change.
