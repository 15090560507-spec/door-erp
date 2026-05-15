# ===================== 西州将军铜门 - 后端 Dockerfile =====================
# 构建上下文：项目根目录 (F:\Door)
FROM python:3.12-slim

WORKDIR /app

# 替换为清华源加速（国内服务器构建）
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
# - gcc libc6-dev: ezdxf 编译需要
# - libreoffice-calc: Excel → PDF 渲染（与 Office 相同布局引擎）
# - poppler-utils: PDF → JPG 转换
# - fonts-noto-cjk: Google Noto CJK 全字重（Serif + Sans），兼容中日韩
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libc6-dev \
        libreoffice-calc \
        poppler-utils \
        fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端源码和 CAD 模板
COPY backend/ .
COPY template.dxf .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
