"""
报价单 Excel 生成 + JPG 渲染
使用 openpyxl 将报价数据写入 template.xlsx 模板
使用 LibreOffice + poppler-utils 将 Excel A1:J24 精确渲染为 JPG
"""
import os
import subprocess
import shutil
import tempfile
from openpyxl import load_workbook
from PIL import Image

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "template.xlsx")


def generate_excel(quote: dict, output_path: str):
    """
    将报价数据写入 Excel 模板并保存到 output_path。
    quote: QuoteResponse dict（包含 customerName, projectName, quoteDate, items）
    """
    wb = load_workbook(TEMPLATE_PATH)
    ws = wb["Sheet1 (2)"] if "Sheet1 (2)" in wb.sheetnames else wb.worksheets[0]

    # Header
    ws["C3"] = quote.get("customerName", "")
    ws["C4"] = quote.get("projectName", "")
    ws["I3"] = quote.get("quoteDate", "")

    items = quote.get("items", [])[:8]

    # Clear and set formulas for rows 9-16
    for row in range(9, 17):
        ws[f"B{row}"] = None
        ws[f"D{row}"] = None
        ws[f"E{row}"] = None
        ws[f"F{row}"] = None
        ws[f"G{row}"] = None
        ws[f"I{row}"] = None
        ws[f"A{row}"] = f'=IF(B{row}<>"",COUNTA($B$9:B{row}),"")'
        ws[f"H{row}"] = f'=IF(OR(D{row}="",E{row}=""),"",D{row}*E{row}*0.000001)'
        ws[f"J{row}"] = f'=IF(OR(H{row}="",I{row}=""),"",ROUND(H{row}*I{row},0))'

    # Fill items
    for index, item in enumerate(items):
        row = 9 + index
        ws[f"B{row}"] = item.get("productName") or item.get("product_name", "")
        ws[f"D{row}"] = item.get("width")
        ws[f"E{row}"] = item.get("height")
        ws[f"F{row}"] = item.get("openDirection") or item.get("open_direction", "")
        ws[f"G{row}"] = item.get("unit") or "m2"
        ws[f"I{row}"] = item.get("unitPrice") or item.get("unit_price", 0)

    ws["J17"] = "=SUM(J9:J16)"
    ws["F18"] = '=IF(J17=0,"",TEXT(J17,"[dbnum2]人民币0元整"))'

    ws.print_area = "A1:J24"
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.save(output_path)


# ===================== JPG 渲染：Excel A1:J24 → 图片 =====================

def render_quote_jpg(quote: dict, output_path: str):
    """
    将报价数据渲染为 JPG 图片（Excel A1:J24 + 40px 白边）。
    管线：openpyxl 生成 Excel → LibreOffice 渲染为 PDF → pdftoppm 转 JPG → Pillow 加白边。
    输出与 Excel 原生导出 A1:J24 完全一致。
    """
    work_dir = tempfile.mkdtemp()

    try:
        # 1. 生成 Excel
        xlsx_path = os.path.join(work_dir, "quote.xlsx")
        generate_excel(quote, xlsx_path)

        # 2. LibreOffice headless: xlsx → PDF
        subprocess.run(
            ["libreoffice", "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", work_dir, xlsx_path],
            check=True, timeout=60, capture_output=True,
        )

        # 找到输出的 PDF 文件
        pdf_files = [f for f in os.listdir(work_dir) if f.endswith(".pdf")]
        if not pdf_files:
            raise RuntimeError("LibreOffice 未生成 PDF")
        pdf_path = os.path.join(work_dir, pdf_files[0])

        # 3. pdftoppm: PDF → JPEG（200 DPI）
        jpg_base = os.path.join(work_dir, "page")
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "200", "-singlefile", pdf_path, jpg_base],
            check=True, timeout=30, capture_output=True,
        )
        raw_jpg = jpg_base + ".jpg"
        if not os.path.exists(raw_jpg):
            raise RuntimeError("pdftoppm 未生成 JPG")

        # 4. Pillow: 加 40px 白边
        with Image.open(raw_jpg) as img:
            margin = 40
            new_w = img.width + 2 * margin
            new_h = img.height + 2 * margin
            out = Image.new("RGB", (new_w, new_h), "#FFFFFF")
            out.paste(img, (margin, margin))
            out.save(output_path, "JPEG", quality=92)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
