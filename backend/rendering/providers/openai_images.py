import json
import urllib.error
import urllib.request
import uuid

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
        if api_type == "openai_images_generations":
            payload = {
                "model": request.config.get("model"),
                "prompt": request.prompt,
                "size": _normalize_size(request.size),
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
                "model": request.config.get("model", ""),
                "prompt": _prompt_with_labels(request),
                "size": _normalize_size(request.size),
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


def _normalize_size(size: str) -> str:
    value = (size or "").strip()
    return "1024x1024" if value in {"", "original"} else value


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
