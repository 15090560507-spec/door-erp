"""
报价系统 API 路由
"""
from fastapi import APIRouter, HTTPException, Query
from quote_models import (
    AccessoryCreate, AccessoryImport,
    QuoteCreate,
    AiConfigUpdate,
)
from quote_database import AccessoryDatabaseManager, QuoteDatabaseManager, AiConfigManager

quote_router = APIRouter()

# 实例化管理器
accessory_db = AccessoryDatabaseManager()
quote_db = QuoteDatabaseManager()
ai_config_db = AiConfigManager()


# ===================== 配件管理 =====================

@quote_router.get("/api/accessories")
def list_accessories(q: str = Query(None, description="搜索关键词")):
    """获取配件列表，支持按名称/类别/型号/关键词搜索"""
    if q:
        accessories = accessory_db.search(q)
    else:
        accessories = accessory_db.get_all()
    return {"accessories": accessories}


@quote_router.post("/api/accessories", status_code=201)
def create_accessory(data: AccessoryCreate):
    """新增配件"""
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="配件名称不能为空")
    try:
        new_acc = accessory_db.add(data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": new_acc["id"]}


# NOTE: export/import 路由必须放在 /{accessory_id} 之前，避免 FastAPI 路由冲突
@quote_router.get("/api/accessories/export")
def export_accessories():
    """导出所有有效配件为 JSON"""
    accessories = accessory_db.get_all()
    return {"accessories": accessories}


@quote_router.post("/api/accessories/import", status_code=201)
def import_accessories(data: AccessoryImport):
    """批量导入配件"""
    items = [item.model_dump() for item in data.accessories]
    count = accessory_db.import_batch(items)
    return {"imported": count}


@quote_router.delete("/api/accessories/{accessory_id}")
def delete_accessory(accessory_id: int):
    """软删除配件（将 active 置为 0）"""
    try:
        accessory_db.soft_delete(accessory_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": accessory_id}


# ===================== 报价单管理 =====================

@quote_router.get("/api/quotes")
def list_quotes():
    """获取报价单列表（最新 50 条，不含 items 明细以优化性能）"""
    quotes = quote_db.get_all(limit=50)
    return {"quotes": quotes}


@quote_router.post("/api/quotes", status_code=201)
def create_quote(data: QuoteCreate):
    """创建报价单"""
    try:
        quote = quote_db.create(data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"quote": quote}


@quote_router.get("/api/quotes/{quote_id}")
def get_quote(quote_id: int):
    """获取单个报价单详情（含 items）"""
    quote = quote_db.get_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="报价单不存在")
    return {"quote": quote}


@quote_router.delete("/api/quotes/{quote_id}")
def delete_quote(quote_id: int):
    """删除报价单"""
    try:
        quote_db.delete(quote_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="报价单不存在")
    return {"deleted": quote_id}


# ===================== 报价单导出（占位） =====================

@quote_router.get("/api/quotes/{quote_id}/export.xlsx")
def export_quote_xlsx(quote_id: int):
    """导出报价单为 Excel（功能开发中）"""
    return {"message": "Excel export coming soon"}


@quote_router.get("/api/quotes/{quote_id}/export.jpg")
def export_quote_jpg(quote_id: int):
    """导出报价单为 JPG（功能开发中）"""
    return {"message": "JPG export coming soon"}


@quote_router.get("/api/quotes/{quote_id}/export.pdf")
def export_quote_pdf(quote_id: int):
    """导出报价单为 PDF（功能开发中）"""
    return {"message": "PDF export coming soon"}


# ===================== AI 配置管理 =====================

@quote_router.get("/api/ai-config")
def get_ai_config():
    """获取 AI 识别配置"""
    config = ai_config_db.get()
    return {"config": config}


@quote_router.post("/api/ai-config")
def update_ai_config(data: AiConfigUpdate):
    """更新 AI 识别配置"""
    config = ai_config_db.update(data.model_dump())
    return {"config": config}


# ===================== 图纸分析（占位） =====================

@quote_router.post("/api/drawings/analyze")
def analyze_drawing():
    """AI 分析图纸（功能开发中）"""
    return {"message": "AI analysis coming soon"}
