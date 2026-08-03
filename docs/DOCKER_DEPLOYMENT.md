# 智能旅行助手 — 容器部署指南

> 本文档介绍如何使用 Docker / Docker Compose 一键部署智能旅行助手前后端服务, 针对**国内网络环境**进行了优化。
>
> - **后端**: Python 3.11 + FastAPI + LangGraph, 通过 **HTTP 传输**连接高德 MCP 远程服务
> - **前端**: Vue 3 静态产物由 nginx 提供, 并反向代理 `/api` 到后端容器
>
> 适用版本: v2.0.0  |  更新日期: 2026-08-02

---

## 目录

1. [部署架构](#1-部署架构)
2. [国内网络优化说明](#2-国内网络优化说明)
3. [前置条件](#3-前置条件)
4. [准备密钥](#4-准备密钥)
5. [快速启动 (推荐)](#5-快速启动-推荐)
6. [服务访问与健康检查](#6-服务访问与健康检查)
7. [配置项详解](#7-配置项详解)
8. [镜像单独构建与运行](#8-镜像单独构建与运行)
9. [生产环境建议](#9-生产环境建议)
10. [常见问题 (FAQ)](#10-常见问题-faq)

---

## 1. 部署架构

```
                    浏览器 :8080
                        │
        ┌───────────────▼─────────────────────┐
        │   frontend 容器 (nginx:alpine)       │
        │   - 静态文件 /usr/share/nginx/html   │
        │   - /api/*  ──反代──► backend:8000   │
        │   - /      ──try_files─► /index.html │
        └───────────────┬─────────────────────┘
                        │ docker network: trip-net
        ┌───────────────▼──────────────────────────┐
        │ backend 容器 (python:3.11-slim)           │
        │  - uvicorn app.api.main:app :8000         │
        │  - 高德 MCP (HTTP) ──► mcp.amap.com/mcp    │
        │  - 高德 REST API ──► restapi.amap.com      │
        │  - LLM API (DeepSeek / Qwen / OpenAI)     │
        └────────────────────────────────────────────┘
```

**关键设计点**:

| 决策 | 原因 |
|------|------|
| 后端通过 HTTP 连接高德 MCP 远程服务 | 代码 `mcp_lifecycle.py` 使用 `transport: "http"` 连接 `https://mcp.amap.com/mcp`, 无需本地 `uvx`/`amap-mcp-server` 子进程, 镜像更精简 |
| 前端构建时注入 `VITE_API_BASE_URL=/` | 让 axios 走同源请求, 由 nginx 反代到后端, 避免跨域 |
| 前端构建期注入 `VITE_AMAP_*` | Vite 会把变量编译进静态产物, 必须在 `build` 阶段提供 |
| LLM/AMAP 密钥通过 `--env-file` 注入 | 敏感信息不进入镜像, 镜像可安全分发 |
| pip 使用清华源, npm 使用 npmmirror | 国内网络加速依赖安装 |
| 后端默认不映射到宿主机 | 仅容器内网可访问, 由 nginx 统一入口更安全 |

---

## 2. 国内网络优化说明

本部署已针对国内网络环境做了以下优化, **无需额外配置**:

| 组件 | 加速措施 | 配置位置 |
|------|---------|---------|
| Python pip | 清华大学 PyPI 源 `pypi.tuna.tsinghua.edu.cn` | [backend/Dockerfile](../backend/Dockerfile) |
| npm | npmmirror 源 `registry.npmmirror.com` | [frontend/Dockerfile](../frontend/Dockerfile) |
| 高德 MCP | `mcp.amap.com` 本身为国内服务, 直连快 | 代码内置 |
| 高德 REST API | `restapi.amap.com` 本身为国内服务, 直连快 | 代码内置 |
| DeepSeek API | `api.deepseek.com` 本身为国内服务 | `.env.docker` |

> 如 Docker Hub 拉取基础镜像 (`python:3.11-slim`, `node:20-alpine`, `nginx:alpine`) 较慢,
> 可配置 Docker 镜像加速器。详见 [附录 A](#附录-a-配置-docker-镜像加速器)。

---

## 3. 前置条件

| 软件 | 最低版本 | 验证命令 |
|------|---------|---------|
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose | v2.20+ | `docker compose version` |

> Compose 命令使用新版 `docker compose` (空格), 而非旧版 `docker-compose` (连字符)。

---

## 4. 准备密钥

部署前请先获取以下密钥:

### 4.1 LLM API Key (必填)

兼容 OpenAI API 的任意服务商均可, 推荐:

| 服务商 | Base URL | 申请地址 |
|--------|---------|---------|
| **DeepSeek** (推荐, 国内快) | `https://api.deepseek.com` | <https://platform.deepseek.com/api_keys> |
| **通义千问** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | <https://dashscope.console.aliyun.com> |
| OpenAI | `https://api.openai.com/v1` | <https://platform.openai.com/api-keys> |

### 4.2 高德地图 Key (必填, 两个)

控制台: <https://console.amap.com/dev/key/app>

| Key 类型 | 用途 | 注入变量 |
|---------|------|---------|
| **Web 服务 API Key** | 后端 POI 搜索 / 天气 / 路线 / MCP 连接 / POI 图片 | `AMAP_API_KEY` |
| **Web 端 JS API Key** | 浏览器地图渲染 | `VITE_AMAP_WEB_JS_KEY` |

> 高德的 "Web 服务 API Key" 与 "Web 端 JS API Key" 是两个独立 Key, 需分别申请。
> JS API Key 还需在控制台配置安全域名 (如 `localhost:8080` 或你的部署域名)。

---

## 5. 快速启动 (推荐)

### 5.1 准备环境文件

```bash
cd trip-planner
cp .env.docker.example .env.docker
```

编辑 `.env.docker`, 至少填入以下 5 项:

```dotenv
# LLM
LLM_MODEL_ID=deepseek-chat
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com

# 高德
AMAP_API_KEY=你的高德Web服务Key
VITE_AMAP_WEB_JS_KEY=你的高德Web端JS_Key
```

### 5.2 构建并启动

```bash
docker compose --env-file .env.docker up -d --build
```

首次构建约 3~5 分钟 (下载基础镜像 + 安装依赖)。构建完成后容器会自动启动。

### 5.3 查看启动状态

```bash
# 容器状态 (等待 backend 变为 healthy)
docker compose ps

# 后端日志 (重点观察 MCP 是否加载成功)
docker compose logs -f backend
```

预期日志片段:

```
🚀 智能旅行助手 v1.0.0
高德地图API Key: 已配置
LLM API Key: 已配置
🔄 正在初始化MCP客户端...
✅ MCP客户端初始化成功
   已加载 16 个工具:
     - maps_text_search: ...
     ...
📚 API文档: http://localhost:8000/docs
```

看到 `✅ MCP客户端初始化成功` 与 `已加载 N 个工具` 即代表后端就绪。

---

## 6. 服务访问与健康检查

| 入口 | 地址 | 说明 |
|------|------|------|
| 前端应用 | <http://localhost:8080> | 主入口 |
| 后端 API | <http://localhost:8080/api/*> | 经 nginx 反代 |
| 健康检查 | <http://localhost:8080/health> | 返回 MCP 工具加载状态 |
| FastAPI Swagger | <http://localhost:8080/docs> | 交互式 API 文档 |
| ReDoc | <http://localhost:8080/redoc> | API 文档 |

> 端口 `8080` 可通过 `.env.docker` 中的 `FRONTEND_PORT` 修改。

如需从宿主机直接访问后端 (绕过 nginx, 如调试用), 在 [docker-compose.yml](../docker-compose.yml) 取消注释:

```yaml
backend:
  ports:
    - "8000:8000"
```

---

## 7. 配置项详解

### 7.1 环境变量 (`.env.docker`)

| 变量 | 必填 | 默认 | 说明 |
|------|:----:|------|------|
| `LLM_MODEL_ID` | ✅ | — | 模型名称, 如 `deepseek-chat` / `qwen-plus` |
| `LLM_API_KEY` | ✅ | — | LLM 服务商 API Key |
| `LLM_BASE_URL` | ✅ | — | OpenAI 兼容 API 地址 |
| `LLM_TIMEOUT` | ➖ | 60 | LLM 调用超时 (秒) |
| `AMAP_API_KEY` | ✅ | — | 高德 Web 服务 API Key |
| `VITE_AMAP_WEB_JS_KEY` | ✅ | — | 高德 JS API Key (前端地图) |
| `FRONTEND_PORT` | ➖ | 8080 | 前端宿主机端口 |
| `CORS_ORIGINS` | ➖ | `http://localhost:8080` | CORS 白名单, 逗号分隔 |
| `LOG_LEVEL` | ➖ | INFO | 日志级别 |

### 7.2 前端构建期变量

以下变量在 `docker compose build` 时通过 `args` 传入, **修改后必须重建前端镜像**:

| 变量 | 值 | 说明 |
|------|-----|------|
| `VITE_API_BASE_URL` | `/` | 固定, 让前端走同源 (nginx 反代) |
| `VITE_AMAP_WEB_KEY` | `$AMAP_API_KEY` | 自动取自 `.env.docker` |
| `VITE_AMAP_WEB_JS_KEY` | 来自 `.env.docker` | 高德 JS API Key |

> 修改前端密钥后: `docker compose --env-file .env.docker up -d --build frontend`

### 7.3 端口规划

| 服务 | 容器端口 | 宿主机映射 | 备注 |
|------|---------|-----------|------|
| frontend | 80 | 8080 (可配) | 唯一对外端口 |
| backend | 8000 | 不映射 | 仅容器内网 |

---

## 8. 镜像单独构建与运行

### 8.1 仅构建镜像

```bash
# 后端
docker build -t trip-planner-backend:latest -f backend/Dockerfile backend/

# 前端 (需传入 build-args)
docker build -t trip-planner-frontend:latest \
  -f frontend/Dockerfile \
  --build-arg VITE_API_BASE_URL=/ \
  --build-arg VITE_AMAP_WEB_KEY=$AMAP_KEY \
  --build-arg VITE_AMAP_WEB_JS_KEY=$AMAP_JS_KEY \
  frontend/
```

### 8.2 独立容器运行 (不用 compose)

需先创建网络, 否则 nginx 无法通过 `backend` 主机名访问后端:

```bash
docker network create trip-net

# 后端
docker run -d --name trip-planner-backend \
  --network trip-net --network-alias backend \
  --env-file .env.docker \
  -e HOST=0.0.0.0 -e PORT=8000 \
  trip-planner-backend:latest

# 前端
docker run -d --name trip-planner-frontend \
  --network trip-net \
  -p 8080:80 \
  trip-planner-frontend:latest
```

---

## 9. 生产环境建议

### 9.1 HTTPS / 反向代理前置

生产环境建议在前面再套一层反向代理 (Nginx / Caddy / Traefik) 处理 TLS:

```
Internet ──► [Caddy:443] ──► frontend:80 ──► (静态)
                              └──► backend:8000 ──► 高德 MCP (HTTP)
```

最简 Caddyfile 示例 (自动 HTTPS):

```caddyfile
trip.example.com {
    reverse_proxy trip-planner-frontend:80
}
```

此时 `.env.docker` 中 `CORS_ORIGINS` 应改为 `https://trip.example.com`:

```dotenv
CORS_ORIGINS=https://trip.example.com
```

### 9.2 多 worker / 性能

后端默认单 uvicorn worker。如需扩容, 修改 [backend/Dockerfile](../backend/Dockerfile) CMD:

```dockerfile
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

> MCP 通过 HTTP 连接远程服务, 多 worker 不会创建额外子进程, 内存占用稳定。
> 建议 worker 数 ≤ CPU 核数。

### 9.3 资源限制

在 [docker-compose.yml](../docker-compose.yml) 添加:

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
```

### 9.4 镜像分发

镜像本身不含密钥, 可推送到私有仓库:

```bash
docker tag trip-planner-backend:latest registry.example.com/trip-planner-backend:latest
docker push registry.example.com/trip-planner-backend:latest
```

---

## 10. 常见问题 (FAQ)

### Q1: 后端日志报 "❌ 配置验证失败: AMAP_API_KEY未配置"

`.env.docker` 中未设置 `AMAP_API_KEY`, 或 `docker compose` 未带 `--env-file .env.docker`。

### Q2: 后端日志报 "MCP客户端初始化失败" 或 "已加载 0 个工具"

当前 MCP 使用 HTTP 传输连接 `https://mcp.amap.com/mcp`, 可能原因:

1. **`AMAP_API_KEY` 错误或失效** — 到 [高德控制台](https://console.amap.com/dev/key/app) 确认 Key 有效。
2. **容器无法访问外网** — 检查容器 DNS 与出网: `docker compose exec backend curl -s https://mcp.amap.com`
3. **高德 MCP 服务暂时不可用** — 稍后重试。

排查命令:

```bash
# 进入后端容器测试网络
docker compose exec backend python -c "import httpx; print(httpx.get('https://mcp.amap.com/mcp').status_code)"

# 检查高德 REST API 是否可达
docker compose exec backend curl -s "https://restapi.amap.com/v3/place/text?keywords=北京&key=$AMAP_API_KEY"
```

### Q3: 前端打开是白屏 / 控制台报跨域错误

- 检查前端构建时 `VITE_API_BASE_URL` 是否为 `/` (在 docker-compose.yml 的 args 中已固定)。
- 浏览器 Network 面板, 请求应发到 `http://<host>:8080/api/...` 而非 `localhost:8000`。

### Q4: `docker compose up` 后前端报 502 Bad Gateway

后端尚未就绪。检查:

```bash
docker compose ps                 # backend 是否 healthy
docker compose logs --tail=100 backend
```

`depends_on: condition: service_healthy` 已确保前端仅在 backend 健康后启动。
若 30 秒内 MCP 仍初始化失败, 可调大 `start_period`。

### Q5: 想修改前端访问端口 (如 80)

编辑 `.env.docker`:

```dotenv
FRONTEND_PORT=80
```

然后重启: `docker compose --env-file .env.docker up -d`

### Q6: 停止与清理

```bash
# 停止容器 (保留镜像)
docker compose down

# 停止并删除镜像
docker compose down --rmi local

# 彻底清理 (含网络)
docker compose down --rmi local --volumes --remove-orphans
```

### Q7: 修改后端代码后如何生效

```bash
docker compose --env-file .env.docker up -d --build backend
```

### Q8: 修改前端代码或密钥后如何生效

```bash
# 修改 .env.docker 中的 VITE_AMAP_* 后必须重建前端
docker compose --env-file .env.docker up -d --build frontend
```

---

## 附录 A: 配置 Docker 镜像加速器

如拉取 Docker Hub 基础镜像较慢, 可配置镜像加速器:

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

> 加速器地址可能随时间失效, 请搜索 "Docker 镜像加速 2026" 获取最新可用地址。

---

## 附录: 文件清单

| 文件 | 用途 |
|------|------|
| [backend/Dockerfile](../backend/Dockerfile) | 后端镜像构建 (Python + pip 清华源) |
| [frontend/Dockerfile](../frontend/Dockerfile) | 前端镜像构建 (多阶段: node 构建 + nginx 托管) |
| [frontend/nginx.conf](../frontend/nginx.conf) | nginx 静态托管 + 反向代理 + SPA 回退 |
| [docker-compose.yml](../docker-compose.yml) | 编排前后端 |
| [.dockerignore](../.dockerignore) | 排除本地开发文件 |
| [.env.docker.example](../.env.docker.example) | 环境变量模板 |

---

**智能旅行助手** — 一键 `docker compose up`, 让旅行规划变得简单而智能
