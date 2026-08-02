# 后端镜像 — Python 3.11 + FastAPI + LangGraph
# MCP 已改为 HTTP 传输连接高德远程服务 (https://mcp.amap.com/mcp)
# 无需 uvx / amap-mcp-server 子进程

FROM python:3.11-slim

# 国内网络优化: 使用清华 PyPI 源加速依赖安装
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

WORKDIR /app

# 先复制依赖声明, 利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口 (容器内部)
EXPOSE 8000

# 运行 uvicorn (生产模式: 关闭 reload)
# 使用 --host 0.0.0.0 确保容器内可访问
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
