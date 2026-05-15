# ===================== 西州将军铜门 - 前端 Dockerfile =====================
FROM node:22-alpine AS base

# ========================= 依赖安装 =========================
FROM base AS deps
WORKDIR /app

# 替换 Alpine 源为阿里云镜像 + 配置 NPM 淘宝镜像（国内服务器加速）
RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.aliyun.com|g' /etc/apk/repositories && \
    npm config set registry https://registry.npmmirror.com/

COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# ========================= 构建阶段 =========================
FROM base AS builder
WORKDIR /app

# Alpine 源 + NPM 淘宝镜像（国内服务器加速）
RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.aliyun.com|g' /etc/apk/repositories && \
    npm config set registry https://registry.npmmirror.com/

COPY package.json package-lock.json* ./
RUN npm ci
COPY . .

# 构建时注入 API 地址，Next.js 会在 bake 阶段内联 NEXT_PUBLIC_* 环境变量
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ========================= 运行阶段 =========================
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
