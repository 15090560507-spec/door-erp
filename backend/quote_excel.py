"""
报价单 Excel 生成 + JPG 渲染
使用 openpyxl 将报价数据写入 template.xlsx 模板
使用 Pillow 将 Excel A1:J24 渲染为 JPG 图片（云端兼容）
"""
import os
import platform
from io import BytesIO
from openpyxl import load_workbook
from PIL import Image, ImageDraw, ImageFont

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "template.xlsx")

# ---- CJK 字体查找 ----
def _find_cjk_font() -> str:
    """查找可用的 CJK 字体，返回字体文件路径"""
    candidates = []
    system = platform.system()
    if system == "Windows":
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/Deng.ttf",
        ]
    elif system == "Linux":
        candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]
    # Darwin (macOS)
    for p in candidates:
        if os.path.exists(p):
            return p
    # Fallback: try Pillow default
    return ""


_CJK_FONT_PATH = _find_cjk_font()


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取指定大小的字体（优先 CJK，回退默认）"""
    if _CJK_FONT_PATH:
        return ImageFont.truetype(_CJK_FONT_PATH, size)
    return ImageFont.load_default()


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

def _to_chinese_amount(n: int) -> str:
    """数字转中文大写金额（用于 JPG 渲染，无需依赖 Excel 公式）"""
    if n == 0:
        return "零元整"
    digits = "零壹贰叁肆伍陆柒捌玖"
    units_small = ["", "拾", "佰", "仟"]
    units_big = ["", "万", "亿"]
    s = str(n)
    length = len(s)
    result = ""
    zero_flag = False
    for i, ch in enumerate(s):
        d = int(ch)
        pos = length - i - 1
        if d == 0:
            zero_flag = True
        else:
            if zero_flag:
                result += "零"
                zero_flag = False
            result += digits[d] + units_small[pos % 4]
        if pos % 4 == 0 and pos > 0:
            result += units_big[pos // 4]
            zero_flag = False
    result += "元整"
    return result


def render_quote_jpg(quote: dict, output_path: str):
    """
    将报价数据渲染为 JPG 图片（Excel A1:J24 布局 + 40px 白边）。
    纯 Python 实现，无需 LibreOffice，云端 Linux 兼容。
    """
    # ---- 列定义 ----
    COL_WIDTHS = [44, 172, 58, 58, 58, 44, 62, 62, 78, 54]
    TOTAL_W = sum(COL_WIDTHS)
    COL_X = [0]
    for w in COL_WIDTHS[:-1]:
        COL_X.append(COL_X[-1] + w)

    # ---- 行定义（24 行 = A1:A24） ----
    TITLE_H = 32
    META_H = 26
    HEADER_H = 28
    DATA_H = 30
    TOTAL_H = 28
    FOOTER_H = 22
    ROW_HEIGHTS = (
        [TITLE_H, TITLE_H]           # 行 1-2: 标题
        + [META_H] * 3               # 行 3-5: 客户/日期/项目
        + [20] * 2                   # 行 6-7: 留白
        + [HEADER_H, HEADER_H]       # 行 8-9: 表头
        + [DATA_H] * 8               # 行 10-17: 数据
        + [TOTAL_H] * 2              # 行 18-19: 合计 + 大写
        + [FOOTER_H] * 5             # 行 20-24: 条款
    )
    TOTAL_H_PX = sum(ROW_HEIGHTS)
    ROW_Y = [0]
    for h in ROW_HEIGHTS[:-1]:
        ROW_Y.append(ROW_Y[-1] + h)

    MARGIN = 40
    IMG_W = TOTAL_W + MARGIN * 2
    IMG_H = TOTAL_H_PX + MARGIN * 2

    # ---- 创建画布 ----
    img = Image.new("RGB", (IMG_W, IMG_H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    font_title = _get_font(18)
    font_bold = _get_font(13)
    font_normal = _get_font(12)
    font_small = _get_font(10)
    font_tiny = _get_font(9)

    BLACK = "#1C1C1E"
    GRAY = "#8E8E93"
    LIGHT_BG = "#F5F5F5"
    BORDER = "#333333"
    THIN_BORDER = "#CCCCCC"

    def mx(x): return MARGIN + x
    def my(y): return MARGIN + y
    def cell_rect(col_start, col_end, row_start, row_end):
        """返回 (x1, y1, x2, y2) 的矩形"""
        return (
            mx(COL_X[col_start]),
            my(ROW_Y[row_start]),
            mx(COL_X[col_end - 1] + COL_WIDTHS[col_end - 1]),
            my(ROW_Y[row_end - 1] + ROW_HEIGHTS[row_end - 1]),
        )

    def draw_text(text, col, row, font=None, color=None, align="left", valign="center", col_end=None):
        """在指定单元格中绘制文字（col_end 用于跨列合并）"""
        if font is None:
            font = font_normal
        if color is None:
            color = BLACK
        ec = col_end if col_end else col + 1
        x, y, x2, y2 = cell_rect(col, ec, row, row + 1)
        bbox = draw.textbbox((0, 0), str(text or ""), font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if align == "center":
            tx = x + (x2 - x - tw) / 2
        elif align == "right":
            tx = x2 - tw - 4
        else:
            tx = x + 4
        if valign == "center":
            ty = y + (y2 - y - th) / 2
        elif valign == "bottom":
            ty = y2 - th - 2
        else:
            ty = y + 2
        draw.text((tx, ty), str(text or ""), fill=color, font=font)

    def draw_rect(col_start, col_end, row_start, row_end, fill=None, outline=None, width=1):
        """绘制矩形"""
        x1, y1, x2, y2 = cell_rect(col_start, col_end, row_start, row_end)
        if fill:
            draw.rectangle([x1, y1, x2, y2], fill=fill)
        if outline:
            draw.rectangle([x1, y1, x2, y2], outline=outline, width=width)

    def draw_line(x1, y1, x2, y2, color=None, width=1):
        if color is None:
            color = BORDER
        draw.line([(mx(x1), my(y1)), (mx(x2), my(y2))], fill=color, width=width)

    # ---- 标题行 ----
    draw_text("浙江西州将军门业有限公司", 0, 0, font=font_title, align="center", col_end=10)
    draw_text("产品报价单", 0, 1, font=font_bold, align="center", col_end=10)

    # ---- Meta 信息 ----
    draw_text("客户名称：", 0, 2, font=font_bold, color=GRAY)
    draw_text(quote.get("customerName", ""), 1, 2)
    draw_text("日期：", 7, 2, font=font_bold, color=GRAY, align="right")
    draw_text(quote.get("quoteDate", ""), 8, 2, align="center")
    draw_text("项目名称：", 0, 3, font=font_bold, color=GRAY)
    draw_text(quote.get("projectName", ""), 1, 3)
    draw_text("主题：", 7, 3, font=font_bold, color=GRAY, align="right")
    draw_text("产品报价单", 8, 3, align="center")

    # ---- 表头（两行：7-8） ----
    header_row1 = 7
    header_row2 = 8
    # 表头背景
    draw_rect(0, 10, header_row1, header_row1 + 2, fill=LIGHT_BG)
    # 表头行1
    draw_text("序号", 0, header_row1, font=font_bold, align="center")
    draw_text("品名型号", 1, header_row1, font=font_bold, align="center")
    # C-D 合并为"规格"
    draw_text("规格", 2, header_row1, font=font_bold, align="center", col_end=4)
    draw_text("开启方向", 4, header_row1, font=font_bold, align="center")
    draw_text("单位", 5, header_row1, font=font_bold, align="center")
    draw_text("数量", 6, header_row1, font=font_bold, align="center")
    draw_text("单价", 7, header_row1, font=font_bold, align="center")
    draw_text("总金额/元", 8, header_row1, font=font_bold, align="center")
    # 表头行2
    draw_text("宽", 2, header_row2, font=font_bold, align="center")
    draw_text("高", 3, header_row2, font=font_bold, align="center")

    # ---- 绘制表头边框 ----
    for col in range(10):
        draw_rect(col, col + 1, header_row1, header_row1 + 2, outline=BORDER)
    # 合并 C-D 行1
    draw.line(
        [(mx(COL_X[3]), my(ROW_Y[header_row1])), (mx(COL_X[3]), my(ROW_Y[header_row1]))], fill=BORDER
    )

    # ---- 数据行 ----
    items = quote.get("items", [])[:8]
    total_amount = 0
    for idx, item in enumerate(items):
        r = 9 + idx
        product = item.get("productName") or item.get("product_name", "")
        width_val = item.get("width")
        height_val = item.get("height")
        direction = item.get("openDirection") or item.get("open_direction", "")
        unit = item.get("unit") or "m²"
        unit_price = item.get("unitPrice") or item.get("unit_price", 0)

        w = float(width_val) if width_val else 0
        h = float(height_val) if height_val else 0
        up = float(unit_price) if unit_price else 0
        qty = w * h * 0.000001 if w and h else 0
        amount = round(qty * up) if qty and up else 0
        total_amount += amount

        draw_text(str(idx + 1), 0, r, font=font_small, align="center", color=GRAY)
        draw_text(product, 1, r, font=font_small)
        draw_text(str(width_val or ""), 2, r, font=font_small, align="center")
        draw_text(str(height_val or ""), 3, r, font=font_small, align="center")
        draw_text(direction, 4, r, font=font_small, align="center")
        draw_text(unit, 5, r, font=font_small, align="center")
        draw_text(f"{qty:.4f}" if qty else "", 6, r, font=font_small, align="center")
        draw_text(str(int(up)) if up else "", 7, r, font=font_small, align="right")
        draw_text(str(amount) if amount else "", 8, r, font=font_small, align="right")
        draw_text("", 9, r, font=font_small)

        # 行边框
        for col in range(10):
            draw_rect(col, col + 1, r, r + 1, outline=THIN_BORDER)

    # ---- 合计行 (17) ----
    draw_rect(0, 10, 17, 18, fill=LIGHT_BG)
    draw_text("合计", 0, 17, font=font_bold, align="right", col_end=7)
    draw_text(str(total_amount), 8, 17, font=font_bold, align="right")
    for col in range(10):
        draw_rect(col, col + 1, 17, 18, outline=BORDER)

    # ---- 大写金额行 (18) ----
    chinese_amt = _to_chinese_amount(total_amount)
    draw_text("合计总金额（大写）：", 0, 18, font=font_bold, color=GRAY)
    draw_text(chinese_amt, 1, 18, font=font_bold, col_end=10)

    # ---- 条款 (20-23) ----
    terms = [
        "本报价不含税工厂结算价，不含木箱。",
        "1. 付款方式：确定制作，先安排货款 50% 的定金，款清发货。",
        "2. 费用说明：以上价格不包含运输、安装、测量等费用。",
        "3. 确认流程：请及时确认签字回传，以便安排生产。",
    ]
    for i, term in enumerate(terms):
        draw_text(term, 0, 20 + i, font=font_tiny, color=GRAY, col_end=10)

    img.save(output_path, "JPEG", quality=92)
