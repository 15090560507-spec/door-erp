from typing import Any, Literal

from pydantic import BaseModel, Field


ASSET_CATEGORIES = ["款式", "花件", "拉手", "锁具", "合页", "颜色", "纹理", "玻璃", "门头", "包套", "其他"]


class ProviderCapabilities(BaseModel):
    textToImage: bool = False
    imageToImage: bool = True
    imageEdit: bool = True
    singleReference: bool = True
    multiReference: bool = True
    inputBase64: bool = True
    inputUrl: bool = False
    sync: bool = True
    asyncTask: bool = False


class RenderModelConfigCreate(BaseModel):
    name: str
    provider: str = "image2_proxy"
    baseUrl: str
    apiKey: str = ""
    model: str
    endpoint: str = "/images/edits"
    apiType: str = "openai_images_edits"
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    defaultSize: str = "original"
    timeoutSeconds: int = 180
    enabled: bool = True


class RenderModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    baseUrl: str | None = None
    apiKey: str | None = None
    model: str | None = None
    endpoint: str | None = None
    apiType: str | None = None
    capabilities: ProviderCapabilities | None = None
    defaultSize: str | None = None
    timeoutSeconds: int | None = None
    enabled: bool | None = None


class RenderAssetUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    remark: str | None = None
    favorite: bool | None = None


class RenderTaskCreate(BaseModel):
    modelConfigId: str
    prompt: str
    size: str = "original"
    count: int = 1
    selectedAssetIds: list[str] = Field(default_factory=list)


class RenderImageResult(BaseModel):
    id: str
    type: Literal["url", "file", "b64_json"]
    src: str
    filePath: str = ""


class RenderTaskResponse(BaseModel):
    id: str
    status: str
    images: list[RenderImageResult] = Field(default_factory=list)
    errorType: str = ""
    errorMessage: str = ""
    upstreamRawError: str = ""
    raw: Any = None

