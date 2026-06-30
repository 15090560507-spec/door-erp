from .openai_images import OpenAIImagesProvider


class Image2ProxyProvider(OpenAIImagesProvider):
    """Default proxy adapter. It follows the selected API Type in model config."""

