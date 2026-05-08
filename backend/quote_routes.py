"""
报价系统 API 路由
"""
import os
import tempfile
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from quote_models import (
    AccessoryCreate, AccessoryImport,
    QuoteCreate,
    AiConfigUpdate,
)
from quote_database import AccessoryDatabaseManager, QuoteDatabaseManager, AiConfigManager
from quote_excel import generate_excel

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


# ===================== 报价单导出 =====================

@quote_router.get("/api/quotes/{quote_id}/export.xlsx")
def export_quote_xlsx(quote_id: int):
    """导出报价单为 Excel"""
    quote = quote_db.get_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="报价单不存在")

    fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        generate_excel(quote, tmp_path)
        filename = f"报价单_{quote.get('customerName', 'export')}_{quote_id}.xlsx"
        return FileResponse(
            tmp_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
            background=None,  # delete temp file after response
        )
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail="Excel 生成失败")


@quote_router.get("/api/quotes/{quote_id}/export.jpg")
def export_quote_jpg(quote_id: int):
    """导出报价单为 JPG — 返回提示，由前端捕获预览区域生成"""
    quote = quote_db.get_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="报价单不存在")
    return {"quote": quote}


@quote_router.get("/api/quotes/{quote_id}/export.pdf")
def export_quote_pdf(quote_id: int):
    """导出报价单为 PDF — 返回 HTML，由前端打开并触发打印"""
    quote = quote_db.get_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="报价单不存在")

    items_html = ""
    items = quote.get("items", [])[:8]
    for i, item in enumerate(items):
        width = item.get("width") or ""
        height = item.get("height") or ""
        unit_price = item.get("unitPrice") or ""
        qty = ""
        amount = ""
        if width and height:
            q = float(width) * float(height) * 0.000001
            qty = f"{q:.4f}"
            if unit_price:
                amount = str(round(q * float(unit_price)))
        items_html += f"""<tr>
            <td>{i + 1}</td>
            <td>{item.get('productName', '')}</td>
            <td>{width}</td><td>{height}</td>
            <td>{item.get('openDirection', '')}</td>
            <td>{item.get('unit', '')}</td>
            <td>{qty}</td><td>{unit_price}</td><td>{amount}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>报价单</title>
<style>
  @page {{ size: A4; margin: 12mm; }}
  body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; font-size: 13px; color: #1C1C1E; }}
  h2 {{ text-align: center; font-size: 18px; margin-bottom: 12px; }}
  .meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 24px; margin-bottom: 10px; }}
  .meta span {{ font-size: 13px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 11px; }}
  th, td {{ border: 1px solid #333; padding: 4px 3px; text-align: center; }}
  th {{ background: #f5f5f5; }}
  .total {{ font-weight: bold; }}
  .terms {{ font-size: 11px; color: #555; margin-top: 10px; }}
</style></head>
<body>
<h2>浙江西州将军门业有限公司</h2>
<div class="meta">
  <div><strong>客户名称：</strong>{quote.get('customerName', '')}</div>
  <div><strong>日期：</strong>{quote.get('quoteDate', '')}</div>
  <div><strong>项目名称：</strong>{quote.get('projectName', '')}</div>
  <div><strong>主题：</strong>产品报价单</div>
</div>
<table>
<thead>
<tr><th rowspan="2">序号</th><th rowspan="2">品名型号</th><th colspan="2">规格</th><th rowspan="2">开启方向</th><th rowspan="2">单位</th><th rowspan="2">数量</th><th rowspan="2">单价</th><th rowspan="2">总金额/元</th></tr>
<tr><th>宽</th><th>高</th></tr>
</thead>
<tbody>{items_html}</tbody>
</table>
<p class="terms">本报价不含税工厂结算价，不含木箱。<br>
1. 付款方式：确定制作，先安排货款 50% 的定金，款清发货。<br>
2. 费用说明：以上价格不包含运输、安装、测量等费用。<br>
3. 确认流程：请及时确认签字回传，以便安排生产。</p>
<script>window.onload=function(){{window.print()}}</script>
</body></html>"""

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


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
