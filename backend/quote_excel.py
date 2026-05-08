"""
报价单 Excel 生成
使用 openpyxl 将报价数据写入 template.xlsx 模板
"""
import os
from openpyxl import load_workbook

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
