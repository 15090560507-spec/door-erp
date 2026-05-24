"""
报价系统 Pydantic 模型
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

DEFAULT_QUOTE_NOTICE_TEXT = "\u672c\u62a5\u4ef7\u4e0d\u542b\u7a0e\u5de5\u5382\u7ed3\u7b97\u4ef7\uff0c\u542b\u6728\u7bb1\u3002"


# ===================== 配件模型 =====================
class AccessoryCreate(BaseModel):
    """新增/更新配件"""
    name: str
    category: str = ""
    model: str = ""
    keywords: str = ""
    unit: str = "m2"
    unitPrice: float = 0.0
    remark: str = ""


class AccessoryResponse(BaseModel):
    """配件响应"""
    id: int
    name: str
    category: str = ""
    model: str = ""
    keywords: str = ""
    unit: str = "m2"
    unitPrice: float = 0.0
    remark: str = ""
    active: int = 1


class AccessoryImport(BaseModel):
    """批量导入配件"""
    accessories: List[AccessoryCreate]


# ===================== 报价单模型 =====================
class QuoteItemRequest(BaseModel):
    """报价明细行"""
    accessoryId: Optional[int] = None
    productName: str
    width: Optional[float] = None
    height: Optional[float] = None
    openDirection: str = ""
    unit: str = "m2"
    unitPrice: float = 0.0


class QuoteCreate(BaseModel):
    """创建报价单"""
    customerName: str
    projectName: str
    quoteDate: str
    noticeText: str = DEFAULT_QUOTE_NOTICE_TEXT
    items: List[QuoteItemRequest]


class QuoteItemResponse(BaseModel):
    """报价明细响应"""
    id: int
    accessoryId: Optional[int] = None
    productName: str
    width: Optional[float] = None
    height: Optional[float] = None
    openDirection: str = ""
    unit: str = "m2"
    unitPrice: float = 0.0
    rowOrder: int


class QuoteResponse(BaseModel):
    """报价单响应"""
    id: int
    customerName: str
    projectName: str
    quoteDate: str
    noticeText: str = DEFAULT_QUOTE_NOTICE_TEXT
    createdAt: str = ""
    items: List[QuoteItemResponse] = []


class QuoteListResponse(BaseModel):
    """报价单列表"""
    quotes: List[QuoteResponse]
    total: int


# ===================== AI 配置模型 =====================
class AiConfigUpdate(BaseModel):
    """更新 AI 配置"""
    baseUrl: str = ""
    endpointPath: str = "/chat/completions"
    apiKey: str = ""
    model: str = ""
    prompt: str = ""


class AiConfigResponse(BaseModel):
    """AI 配置响应"""
    id: int = 1
    baseUrl: str = ""
    endpointPath: str = "/chat/completions"
    apiKey: str = ""
    model: str = ""
    prompt: str = ""
    updatedAt: str = ""


# ===================== 图纸分析模型 =====================
class AnalysisItem(BaseModel):
    """AI 识别出的明细项"""
    productName: str = ""
    width: Optional[float] = None
    height: Optional[float] = None
    openDirection: str = ""
    unit: str = "m2"
    unitPrice: Optional[float] = None


class AnalysisResult(BaseModel):
    """AI 识别结果"""
    customerName: str = ""
    projectName: str = ""
    outerWidth: Optional[float] = None
    outerHeight: Optional[float] = None
    openDirection: str = ""
    items: List[AnalysisItem] = []
    accessories: List[str] = []
    notes: str = ""


class DrawingAnalysisResponse(BaseModel):
    """图纸分析完整响应"""
    uploadId: int
    filename: str
    analysis: AnalysisResult
    rawPreview: str = ""
