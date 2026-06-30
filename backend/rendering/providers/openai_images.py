import json
import math
import re
import urllib.error
import urllib.request
import uuid

from rendering.storage import image_size

from .base import (
    BaseProvider,
    ProviderError,
    RenderProviderRequest,
    auth_headers,
    extract_http_error,
    normalize_images,
    openai_join_url,
    parse_json_response,
)


class OpenAIImagesProvider(BaseProvider):
    def render(self, request: RenderProviderRequest) -> dict:
        api_type = request.config.get("apiType") or "openai_images_edits"
        endpoint = request.config.get("endpoint") or "/images/edits"
        url = openai_join_url(request.config.get("baseUrl", ""), endpoint)
        timeout = int(request.config.get("timeoutSeconds") or 180)
        api_key = request.config.get("apiKey") or ""
        if not api_key:
            raise ProviderError("模型配置缺少 API Key", status_code=400, error_type="config_error")
        image_options = _image2_options(request.size, request.line_art)
        model = _normalize_model(request.config.get("model"))
        if api_type == "openai_images_generations":
            payload = {
                "model": model,
                "prompt": request.prompt,
                "size": image_options["size"],
                "aspect_ratio": image_options["aspect_ratio"],
                "resolution": image_options["resolution"],
                "n": request.count,
            }
            upstream = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=auth_headers(api_key),
                method="POST",
            )
        else:
            fields = {
                "model": model,
                "prompt": _prompt_with_labels(request),
                "size": image_options["size"],
                "aspect_ratio": image_options["aspect_ratio"],
                "resolution": image_options["resolution"],
                "n": str(request.count),
            }
            files = [("image", request.line_art)]
            for item in request.all_references:
                files.append(("image", item))
            body, boundary = _multipart(fields, files)
            upstream = urllib.request.Request(
                url,
                data=body,
                headers=auth_headers(api_key, f"multipart/form-data; boundary={boundary}"),
                method="POST",
            )
        try:
            with urllib.request.urlopen(upstream, timeout=timeout) as response:
                payload = parse_json_response(response)
        except urllib.error.HTTPError as exc:
            raise extract_http_error(exc, url) from exc
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"模型请求失败: {exc}", error_type="request_error") from exc
        images = normalize_images(payload)
        if not images:
            raise ProviderError("模型返回中没有可用图片", error_type="empty_result", raw=str(payload)[:1200])
        return {"images": images, "raw": payload}


def _normalize_model(model: str | None) -> str:
    value = (model or "").strip()
    return "gpt-image-2" if value in {"", "image2"} else value


def _image2_options(size: str, line_art: dict | None = None) -> dict[str, str]:
    value = (size or "original").strip().lower()
    width, height = _source_size(line_art)
    if re.fullmatch(r"\d+x\d+", value):
        width, height = [int(part) for part in value.split("x", 1)]
        aspect_ratio = _closest_aspect_ratio(width, height)
        resolution = _resolution_from_size(width, height)
        return {"size": value, "aspect_ratio": aspect_ratio, "resolution": resolution}

    aspect_ratio = _closest_aspect_ratio(width, height)
    resolution = value if value in {"1k", "2k", "4k"} else _resolution_from_size(width, height)
    out_width, out_height = _size_from_ratio(aspect_ratio, resolution)
    return {"size": f"{out_width}x{out_height}", "aspect_ratio": aspect_ratio, "resolution": resolution}


def _source_size(line_art: dict | None) -> tuple[int, int]:
    try:
        if line_art and line_art.get("filePath"):
            return image_size(line_art["filePath"])
    except Exception:
        pass
    return (1024, 1024)


def _resolution_from_size(width: int, height: int) -> str:
    long_side = max(width, height)
    if long_side > 2600:
        return "4k"
    if long_side > 1300:
        return "2k"
    return "1k"


def _closest_aspect_ratio(width: int, height: int) -> str:
    supported = {
        "1x1": (1, 1),
        "5x4": (5, 4),
        "9x16": (9, 16),
        "21x9": (21, 9),
        "16x9": (16, 9),
        "4x3": (4, 3),
        "3x2": (3, 2),
        "4x5": (4, 5),
        "3x4": (3, 4),
        "2x3": (2, 3),
    }
    target = max(width, 1) / max(height, 1)
    return min(supported, key=lambda key: abs(math.log((supported[key][0] / supported[key][1]) / target)))


def _size_from_ratio(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    base = {"1k": 1024, "2k": 2048, "4k": 4096}.get(resolution, 1024)
    ratio_width, ratio_height = [int(part) for part in aspect_ratio.split("x", 1)]
    if ratio_width >= ratio_height:
        width = base
        height = round(base * ratio_height / ratio_width)
    else:
        height = base
        width = round(base * ratio_width / ratio_height)
    width = max(8, int(round(width / 8)) * 8)
    height = max(8, int(round(height / 8)) * 8)
    return width, height


def _prompt_with_labels(request: RenderProviderRequest) -> str:
    lines = []
    if request.style_reference:
        lines.append("参考款式图: 用于整体门板风格、颜色、纹理和效果")
    for item in request.assets + request.temp_assets:
        label = item.get("category") or item.get("label") or "配件"
        name = item.get("name") or item.get("originalName") or "参考图"
        lines.append(f"{label}: {name}")
    if not lines:
        return request.prompt
    return f"{request.prompt}\n\n参考图说明:\n" + "\n".join(f"{idx + 1}. {text}" for idx, text in enumerate(lines))


def _multipart(fields: dict[str, str], files: list[tuple[str, dict]]) -> tuple[bytes, str]:
    boundary = f"----door-render-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for field_name, file_info in files:
        filename = file_info.get("originalName") or "image.png"
        mime = file_info.get("mimeType") or "image/png"
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
        chunks.append(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
        with open(file_info["filePath"], "rb") as handle:
            chunks.append(handle.read())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), boundary
