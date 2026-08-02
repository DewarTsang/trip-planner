# 前端镜像 — 多阶段构建
# Stage 1: Node 构建 Vue 静态产物
# Stage 2: nginx 托管静态文件 + 反向代理 /api

# ============ Stage 1: 构建 ============
FROM node:20-alpine AS builder

# 国内网络优化: 使用 npmmirror 加速 npm install
RUN npm config set registry https://registry.npmmirror.com

WORKDIR /app

# 先复制依赖声明, 利用层缓存
COPY package.json package-lock.json ./

# 安装依赖 (ci 模式更严格、更快)
RUN npm ci

# 复制源代码
COPY . .

# 构建参数: Vite 编译期注入的环境变量
# VITE_API_BASE_URL 固定为 "/" 让前端走同源 (由 nginx 反代到后端)
ARG VITE_API_BASE_URL=/
ARG VITE_AMAP_WEB_KEY
ARG VITE_AMAP_WEB_JS_KEY

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_AMAP_WEB_KEY=${VITE_AMAP_WEB_KEY}
ENV VITE_AMAP_WEB_JS_KEY=${VITE_AMAP_WEB_JS_KEY}

RUN npm run build

# ============ Stage 2: 托管 ============
FROM nginx:alpine

# 复制自定义 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
