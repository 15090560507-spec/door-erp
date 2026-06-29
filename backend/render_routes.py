"""Render image API for forwarding uploaded references to image generation providers."""
import base64
import json
import re
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

render_router = APIRouter()
MAX_FILE_SIZE = 15 * 1024 * 1024
DEFAULT_SIZE = "1k"
DEFAULT_COUNT = 1


@dataclass(frozen=True)
class RenderEndpoint:
    url: str
    mode: str


@render_router.get("/api/render/health")
def render_health():
    return {"ok": True}


@render_router.post("/api/render/generate")
async def generate_render(
    lineArt: UploadFile = File(...),
    reference: list[UploadFile] = File(...),
    referenceLabels: str = Form("[]"),
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
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing)}")

    references = reference if isinstance(reference, list) else [reference]
    if not references:
        raise HTTPException(status_code=400, detail="At least one reference image is required")
    labels = _parse_reference_labels(referenceLabels, len(references))
    line_bytes = await _read_image_upload(lineArt, "Line art")
    reference_files = []
    for index, item in enumerate(references):
        reference_bytes = await _read_image_upload(item, f"Reference image {index + 1}")
        reference_files.append(
            ("reference", _safe_filename(item.filename, f"reference-{index + 1}.png"), item.content_type or "image/png", reference_bytes)
        )
    endpoint = _build_render_endpoint(base_url)
    if labels:
        label_lines = "\n".join(f"{index + 1}. {label or '参考图'}" for index, label in enumerate(labels))
        prompt_text = f"{prompt_text}\n\n参考图对应内容:\n{label_lines}"
    if endpoint.mode == "ark_images_generations":
        image_inputs = [_image_data_url(line_bytes, lineArt.content_type or "image/png")]
        image_inputs.extend(_image_data_url(data, content_type) for _field, _name, content_type, data in reference_files)
        ark_payload: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt_text,
            "image": image_inputs,
            "size": _normalize_ark_size(image_size),
            "response_format": "url",
            "stream": False,
            "watermark": False,
        }
        if image_count > 1:
            ark_payload["sequential_image_generation"] = "auto"
            ark_payload["sequential_image_generation_options"] = {"max_images": image_count}
        else:
            ark_payload["sequential_image_generation"] = "disabled"
        body = json.dumps(
            ark_payload,
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint.url,
            data=body,
            headers=_build_json_upstream_headers(api_key),
            method="POST",
        )
    else:
        fields = {"model": model_name, "prompt": prompt_text, "size": image_size, "n": str(image_count)}
        files = [
            ("image", _safe_filename(lineArt.filename, "line-art.png"), lineArt.content_type or "image/png", line_bytes),
        ] + reference_files
        body, boundary = _build_multipart(fields, files)
        request = urllib.request.Request(
            endpoint.url,
            data=body,
            headers=_build_upstream_headers(api_key, boundary),
            method="POST",
        )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            content_type = response.headers.get("content-type", "")
            response_text = response.read().decode("utf-8", errors="ignore")
            payload: Any = json.loads(response_text) if "application/json" in content_type else response_text
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        detail = _extract_error_details(body, exc.code, endpoint.url)
        raise HTTPException(status_code=502, detail=f"Image API returned error {exc.code}: {detail}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Render request failed: {_sanitize_error(str(exc))}") from exc

    images = _normalize_images(payload)
    if not images:
        raise HTTPException(status_code=502, detail="The image API response did not include b64_json or url image data")
    raw_count = len(payload.get("data", [])) if isinstance(payload, dict) and isinstance(payload.get("data"), list) else len(images)
    return {"images": images, "rawCount": raw_count}


async def _read_image_upload(file: UploadFile, label: str) -> bytes:
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"{label} must be an image file")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"{label} is empty")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"{label} must be 15MB or smaller")
    return data


def _build_render_endpoint(base_url: str) -> RenderEndpoint:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Base URL must be a valid http or https URL")
    normalized = base_url.rstrip("/")
    path = parsed.path.rstrip("/").lower()
    host = parsed.netloc.lower()
    if host.endswith("volces.com") and path.startswith("/api/v3"):
        if re.search(r"/images/(?:edits|generations|variations)$", path):
            url = re.sub(r"/images/(?:edits|variations)$", "/images/generations", normalized, flags=re.I)
        elif path.endswith("/api/v3"):
            url = f"{normalized}/images/generations"
        else:
            url = normalized
        return RenderEndpoint(url=url, mode="ark_images_generations")
    if re.search(r"/images/(edits|generations|variations)$", path):
        return RenderEndpoint(url=normalized, mode="openai_images_edits")
    if path and not path.endswith("/v1"):
        return RenderEndpoint(url=normalized, mode="openai_images_edits")
    return RenderEndpoint(url=f"{normalized}/images/edits", mode="openai_images_edits")


def _build_upstream_headers(api_key: str, boundary: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 DoorERP/1.0",
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
    }


def _build_json_upstream_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 DoorERP/1.0",
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
    }


def _image_data_url(data: bytes, content_type: str) -> str:
    media_type = content_type if content_type.startswith("image/") else "image/png"
    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"


def _normalize_ark_size(size: str) -> str:
    value = (size or DEFAULT_SIZE).strip()
    if value.lower() in {"1k", "2k", "4k"}:
        return value.upper()
    return value


def _clamp_count(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_COUNT
    return min(max(parsed, 1), 4)


def _parse_reference_labels(raw: str, count: int) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        parsed = []
    if not isinstance(parsed, list):
        parsed = []
    labels = [str(item or "").strip() for item in parsed[:count]]
    while len(labels) < count:
        labels.append("")
    return labels


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


def _extract_error_details(body: str, status: int, upstream_url: str = "") -> str:
    try:
        payload = json.loads(body)
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            message = error.get("message") or error.get("detail") or json.dumps(error, ensure_ascii=False)
        else:
            message = str(error)
    except json.JSONDecodeError:
        message = body or f"HTTP {status}"
    message = _sanitize_error(message)
    safe_url = _safe_url_for_message(upstream_url)
    if status == 404:
        suffix = f" 实际调用地址: {safe_url}" if safe_url else ""
        return (
            "上游图片接口不存在。请确认 Base URL 是图片接口根路径，例如 https://api.example.com/v1；"
            "如果服务商图片接口不是 /images/edits，请直接把完整图片接口地址填到 Base URL。"
            f"{suffix}。原始错误: {_truncate(message, 180)}"
        )
    if status == 403 and re.search(r"(?:code\s*[:=]?\s*)?1010|error\s+1010", message, re.I):
        return (
            "上游图片接口返回 403/1010，通常表示服务商网关拦截或当前 API Key/模型没有图片编辑权限。"
            "请确认 Base URL 指向 OpenAI-compatible 图片接口根路径、模型支持 /images/edits，"
            "并检查该服务商是否限制服务器 IP 或 Cloudflare/WAF 访问。原始错误: "
            f"{_truncate(message, 180)}"
        )
    return _truncate(message, 500)


def _safe_url_for_message(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _sanitize_error(message: str) -> str:
    text = str(message or "")
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [hidden]", text, flags=re.I)
    text = re.sub(r"api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']+[\"']", "api_key: [hidden]", text, flags=re.I)
    return text


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}..."
