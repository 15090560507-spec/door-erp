"""???? API?????? OpenAI-compatible Images Edits ???"""
import json
import re
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

render_router = APIRouter()
MAX_FILE_SIZE = 15 * 1024 * 1024
DEFAULT_SIZE = "1k"
DEFAULT_COUNT = 1


@render_router.get("/api/render/health")
def render_health():
    return {"ok": True}


@render_router.post("/api/render/generate")
async def generate_render(
    lineArt: UploadFile = File(...),
    reference: UploadFile = File(...),
    baseUrl: str = Form(...),
    apiKey: str = Form(...),
    model: str = Form(...),
    prompt: str = Form(...),
    size: str = Form(DEFAULT_SIZE),
    count: int = Form(DEFAULT_COUNT),
):
    base_url = (baseUrl or "").strip()
    api_key = (apiKey or "").strip()
    model_name = (model or "").strip()
    prompt_text = (prompt or "").strip()
    image_size = (size or DEFAULT_SIZE).strip() or DEFAULT_SIZE
    image_count = _clamp_count(count)

    missing = []
    if not base_url:
        missing.append("Base URL")
    if not api_key:
        missing.append("API Key")
    if not model_name:
        missing.append("Model")
    if not prompt_text:
        missing.append("Prompt")
    if missing:
        raise HTTPException(status_code=400, detail=f"????{', '.join(missing)}")

    line_bytes = await _read_image_upload(lineArt, "???")
    reference_bytes = await _read_image_upload(reference, "???")
    upstream_url = _build_images_edits_url(base_url)
    fields = {"model": model_name, "prompt": prompt_text, "size": image_size, "n": str(image_count)}
    files = [
        ("image", _safe_filename(lineArt.filename, "line-art.png"), lineArt.content_type or "image/png", line_bytes),
        ("reference", _safe_filename(reference.filename, "reference.png"), reference.content_type or "image/png", reference_bytes),
    ]
    body, boundary = _build_multipart(fields, files)
    request = urllib.request.Request(
        upstream_url,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            content_type = response.headers.get("content-type", "")
            response_text = response.read().decode("utf-8", errors="ignore")
            payload: Any = json.loads(response_text) if "application/json" in content_type else response_text
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        detail = _extract_error_details(body, exc.code)
        raise HTTPException(status_code=502, detail=f"???????? {exc.code}: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"????????: {_sanitize_error(str(exc))}") from exc

    images = _normalize_images(payload)
    if not images:
        raise HTTPException(status_code=502, detail="???????????? b64_json ? url ??")
    raw_count = len(payload.get("data", [])) if isinstance(payload, dict) and isinstance(payload.get("data"), list) else len(images)
    return {"images": images, "rawCount": raw_count}


async def _read_image_upload(file: UploadFile, label: str) -> bytes:
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"{label}???????")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"{label}??")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"{label}???? 15MB")
    return data


def _build_images_edits_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Base URL ?????? http ? https ??")
    normalized = base_url.rstrip("/")
    if normalized.endswith("/images/edits"):
        return normalized
    return f"{normalized}/images/edits"


def _clamp_count(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_COUNT
    return min(max(parsed, 1), 4)


def _safe_filename(name: str | None, fallback: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "-", str(name or "")).strip()
    return cleaned or fallback


def _build_multipart(fields: dict[str, str], files: list[tuple[str, str, str, bytes]]) -> tuple[bytes, str]:
    boundary = f"----door-render-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for field_name, filename, content_type, data in files:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), boundary


def _normalize_images(payload: Any) -> list[dict[str, str]]:
    candidates: list[Any] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            candidates.extend(payload["data"])
        if payload.get("b64_json") or payload.get("url"):
            candidates.append(payload)
    images = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if item.get("b64_json"):
            value = str(item["b64_json"])
            images.append({"type": "b64_json", "src": value if value.startswith("data:") else f"data:image/png;base64,{value}"})
        elif item.get("url"):
            images.append({"type": "url", "src": str(item["url"])})
    return images


def _extract_error_details(body: str, status: int) -> str:
    try:
        payload = json.loads(body)
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            message = error.get("message") or error.get("detail") or json.dumps(error, ensure_ascii=False)
        else:
            message = str(error)
    except json.JSONDecodeError:
        message = body or f"HTTP {status}"
    return _truncate(_sanitize_error(message), 500)


def _sanitize_error(message: str) -> str:
    text = str(message or "")
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [hidden]", text, flags=re.I)
    text = re.sub(r"api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']+[\"']", "api_key: [hidden]", text, flags=re.I)
    return text


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}..."
