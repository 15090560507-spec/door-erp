import json
import re
import urllib.error
import urllib.request

from rendering.storage import image_size
from .base import (
    BaseProvider,
    ProviderError,
    RenderProviderRequest,
    auth_headers,
    extract_http_error,
    normalize_images,
    parse_json_response,
    read_data_url,
    safe_join_url,
)


class VolcengineArkProvider(BaseProvider):
    def render(self, request: RenderProviderRequest) -> dict:
        url = safe_join_url(request.config.get("baseUrl", ""), request.config.get("endpoint") or "/images/generations")
        url = re.sub(r"/images/(?:edits|variations)$", "/images/generations", url, flags=re.I)
        timeout = int(request.config.get("timeoutSeconds") or 180)
        api_key = request.config.get("apiKey") or ""
        if not api_key:
            raise ProviderError("模型配置缺少 API Key", status_code=400, error_type="config_error")
        images = [read_data_url(request.line_art)]
        images.extend(read_data_url(item) for item in request.all_references)
        payload = {
            "model": request.config.get("model"),
            "prompt": request.prompt,
            "images": images,
            "size": _ark_size(request.size, request.line_art),
            "response_format": "url",
            "sequential_image_generation": "auto" if request.count > 1 else "disabled",
        }
        if request.count > 1:
            payload["sequential_image_generation_options"] = {"max_images": request.count}
        upstream = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=auth_headers(api_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(upstream, timeout=timeout) as response:
                data = parse_json_response(response)
        except urllib.error.HTTPError as exc:
            raise extract_http_error(exc, url) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"模型请求失败: {exc}", error_type="request_error") from exc
        results = normalize_images(data)
        if not results:
            raise ProviderError("模型返回中没有可用图片", error_type="empty_result", raw=str(data)[:1200])
        return {"images": results, "raw": data}


def _ark_size(size: str, line_art: dict) -> str:
    value = (size or "original").strip().lower()
    if value in {"2k", "4k"}:
        return value
    if re.fullmatch(r"\d+x\d+", value):
        return value
    if value == "3k":
        return "2k"
    width, height = image_size(line_art["filePath"])
    target = 2048
    if width >= height:
        out_w = target
        out_h = round(height * target / width)
    else:
        out_h = target
        out_w = round(width * target / height)
    out_w = max(8, int(round(out_w / 8)) * 8)
    out_h = max(8, int(round(out_h / 8)) * 8)
    return f"{out_w}x{out_h}"
