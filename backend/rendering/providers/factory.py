from .base import BaseProvider, ProviderError
from .image2_proxy import Image2ProxyProvider
from .openai_images import OpenAIImagesProvider
from .volcengine_ark import VolcengineArkProvider


def get_provider(name: str) -> BaseProvider:
    normalized = (name or "").strip().lower()
    if normalized in {"image2", "image2_proxy", "proxy"}:
        return Image2ProxyProvider()
    if normalized in {"openai", "openai_compatible", "openai_images"}:
        return OpenAIImagesProvider()
    if normalized in {"volcengine", "volcengine_ark", "ark"}:
        return VolcengineArkProvider()
    raise ProviderError(f"未知 Provider: {name}", status_code=400, error_type="config_error")

