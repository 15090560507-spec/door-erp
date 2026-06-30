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
    return text


def normalize_images(payload: Any) -> list[dict]:
    candidates: list[Any] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            candidates.extend(payload["data"])
        if payload.get("b64_json") or payload.get("url"):
            candidates.append(payload)
        if isinstance(payload.get("images"), list):
            candidates.extend(payload["images"])
    images: list[dict] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if item.get("b64_json"):
            value = str(item["b64_json"])
            images.append({"type": "b64_json", "src": value if value.startswith("data:") else f"data:image/png;base64,{value}"})
        elif item.get("url"):
            images.append({"type": "url", "src": str(item["url"])})
    return images


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
    return ProviderError(_sanitize(message), status_code=502, error_type="upstream_http_error", raw=_sanitize(body)[:1200])


def _safe_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url or "")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _sanitize(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [hidden]", value, flags=re.I)
    value = re.sub(r"api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']+[\"']", "api_key: [hidden]", value, flags=re.I)
    return value

