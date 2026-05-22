# ===================== 西州将军铜门 - 后端 Dockerfile =====================
# 构建上下文：项目根目录 (F:\Door)
FROM python:3.12-slim

WORKDIR /app

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PLAYWRIGHT_EXECUTABLE_PATH=/usr/bin/chromium

# 替换为清华源加速（国内服务器构建）
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
# - libreoffice-calc / poppler-utils：保留旧 Excel 导出链路
# - nodejs / npm / chromium：为 Playwright 报价模板导出提供运行环境
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libc6-dev \
        libreoffice-calc \
        poppler-utils \
        fonts-noto-cjk \
        nodejs \
        npm \
        chromium && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装报价模板依赖
COPY quote-template-pdf/package.json /app/quote-template-pdf/package.json
COPY quote-template-pdf/package-lock.json /app/quote-template-pdf/package-lock.json
RUN cd /app/quote-template-pdf && npm ci --registry=https://registry.npmmirror.com

# 复制后端源码、报价模板工程和 CAD 模板
COPY backend/ .
COPY quote-template-pdf/ /app/quote-template-pdf/
COPY template.xlsx .
COPY template.dxf .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
