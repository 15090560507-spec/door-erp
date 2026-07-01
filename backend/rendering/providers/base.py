import base64
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class RenderProviderRequest:
    config: dict
    prompt: str
    size: str
    count: int
    line_art: dict
    style_reference: dict | None
    assets: list[dict]
    temp_assets: list[dict]

    @property
    def all_references(self) -> list[dict]:
        refs = []
        if self.style_reference:
            refs.append(self.style_reference)
        refs.extend(self.assets)
        refs.extend(self.temp_assets)
        return refs


class ProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502, error_type: str = "provider_error", raw: str = ""):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.raw = raw


class BaseProvider:
    def render(self, request: RenderProviderRequest) -> dict:
        raise NotImplementedError


def auth_headers(api_key: str, content_type: str = "application/json") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": content_type,
        "Accept": "application/json",
        "User-Agent": "DoorERP-Render/1.0",
    }


def read_data_url(file_info: dict) -> str:
    mime = file_info.get("mimeType") or "image/png"
    with open(file_info["filePath"], "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def parse_json_response(response) -> Any:
    content_type = response.headers.get("content-type", "")
    text = response.read().decode("utf-8", errors="ignore")
    if "application/json" in content_type or text.strip().startswith(("{", "[")):
        return json.loads(text)
    if _looks_like_html(text):
        raise ProviderError(
            "上游返回的是网页 HTML，不是图片接口 JSON。通常是 Base URL 或 Endpoint 配错了；New API/OpenAI 兼容接口一般需要 /v1/images/edits 或 /v1/images/generations。",
            status_code=502,
            error_type="upstream_html_response",
            raw=_sanitize(text)[:1200],
        )
    return text


def normalize_images(payload: Any) -> list[dict]:
    images: list[dict] = []
    seen: set[str] = set()

    def add_image(kind: str, value: Any):
        src = str(value or "").strip()
        if not src:
            return
        if kind == "b64_json" and not src.startswith("data:"):
            src = f"data:image/png;base64,{src}"
        if src in seen:
            return
        seen.add(src)
        images.append({"type": kind, "src": src})

    def walk(value: Any, key_hint: str = ""):
        if value is None:
            return
        if isinstance(value, str):
            text = value.strip()
            lower_key = key_hint.lower()
            if text.startswith("data:image/"):
                add_image("b64_json", text)
            elif text.startswith(("http://", "https://")) and _looks_like_image_url_key(lower_key, text):
                add_image("url", text)
            elif lower_key in {"b64_json", "base64", "image_base64", "imagebase64"} and len(text) > 100:
                add_image("b64_json", text)
            return
        if isinstance(value, list):
            for item in value:
                walk(item, key_hint)
            return
        if not isinstance(value, dict):
            return

        for key in ["b64_json", "base64", "image_base64", "imageBase64"]:
            if key in value:
                add_image("b64_json", value.get(key))
        for key in ["url", "image_url", "imageUrl", "image", "output_url", "outputUrl"]:
            if key in value and isinstance(value.get(key), str):
                item = str(value.get(key) or "").strip()
                if item.startswith("data:image/"):
                    add_image("b64_json", item)
                elif item.startswith(("http://", "https://")):
                    add_image("url", item)

        for key, child in value.items():
            walk(child, str(key))

    walk(payload)
    return images


def _looks_like_image_url_key(key: str, value: str) -> bool:
    if any(token in key for token in ["url", "image", "img", "output", "result"]):
        return True
    return bool(re.search(r"\.(png|jpe?g|webp)(?:\?|$)", value, re.I))


def safe_join_url(base_url: str, endpoint: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    path = (endpoint or "").strip()
    if not base:
        raise ProviderError("模型配置缺少 Base URL", status_code=400, error_type="config_error")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderError("Base URL 必须是有效的 http/https 地址", status_code=400, error_type="config_error")
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base}/{path.lstrip('/')}" if path else base


def openai_join_url(base_url: str, endpoint: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    path = (endpoint or "").strip() or "/images/edits"
    if path.startswith("http://") or path.startswith("https://"):
        return path
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderError("Base URL 必须是有效的 http/https 地址", status_code=400, error_type="config_error")
    lower_base_path = parsed.path.rstrip("/").lower()
    clean_path = path.lstrip("/")
    if lower_base_path.endswith("/v1") and clean_path.startswith("v1/"):
        clean_path = clean_path[3:]
    if clean_path.startswith("v1/") or lower_base_path.endswith("/v1"):
        return f"{base}/{clean_path}"
    if clean_path.startswith("images/"):
        return f"{base}/v1/{clean_path}"
    return f"{base}/{clean_path}"


def extract_http_error(exc, url: str = "") -> ProviderError:
    body = exc.read().decode("utf-8", errors="ignore")
    message = body or f"HTTP {exc.code}"
    try:
        payload = json.loads(body)
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            message = error.get("message") or error.get("detail") or json.dumps(error, ensure_ascii=False)
        else:
            message = str(error)
    except Exception:
        pass
    safe_url = _safe_url(url)
    if safe_url:
        message = f"{message}；实际调用地址: {safe_url}"
    status_code = _proxy_status_code(int(exc.code))
    return ProviderError(_sanitize(message), status_code=status_code, error_type="upstream_http_error", raw=_sanitize(body)[:1200])


def _proxy_status_code(upstream_status: int) -> int:
    if upstream_status in {401, 403}:
        return 502
    return upstream_status if 400 <= upstream_status < 500 else 502


def _safe_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url or "")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _sanitize(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [hidden]", value, flags=re.I)
    value = re.sub(r"api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']+[\"']", "api_key: [hidden]", value, flags=re.I)
    return value


def _looks_like_html(text: str) -> bool:
    sample = (text or "").lstrip()[:300].lower()
    return sample.startswith("<!doctype html") or sample.startswith("<html") or "<title>" in sample
