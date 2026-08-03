# 智能旅行助手 🌍✈️

基于 **LangChain + LangGraph** 多智能体框架构建的 AI 旅行规划助手,通过 MCP 协议集成高德地图服务,提供个性化的旅行计划生成。

> 📌 **v2.0.0** — 基于 LangChain + LangGraph 构建。详见 [架构文档](docs/ARCHITECTURE.md)。

## ✨ 功能特点

- 🤖 **LangGraph 多智能体协作**: StateGraph 编排,并行搜索 + 结构化输出 + 图片丰富,智能生成详细的多日旅程
- 🗺️ **高德地图 MCP 集成**: 通过 MCP 协议接入 16 个高德地图工具,支持景点搜索、路线规划、天气查询
- ⚡ **并行工具调用**: asyncio.gather 3 路并发搜索 (景点+天气+酒店),搜索耗时 <1 秒
- 📋 **结构化输出**: `with_structured_output(TripPlan)` 直接生成 Pydantic 对象,无需 JSON 解析
- 🖼️ **景点图片自动获取**: 模糊匹配 POI 后通过高德 REST API 获取真实景点照片,无图时 SVG 渐变占位
- 🛡️ **多级降级**: MCP 不可用→LLM 失败→模板计划,任何情况下都有可用输出
- 🎨 **现代化前端**: Vue 3 + TypeScript + Vite + Ant Design Vue,响应式设计
- 📤 **导出功能**: 行程可导出为 PNG 图片 / PDF 文件

## 🏗️ 技术栈

### 后端
- **框架**: LangChain >=0.3 + LangGraph >=0.3
- **API**: FastAPI >=0.115
- **MCP 集成**: langchain-mcp-adapters >=0.3 + amap-mcp-server
- **LLM**: ChatOpenAI — 支持 OpenAI / DeepSeek / Qwen 等所有 OpenAI 兼容 API
- **数据校验**: Pydantic >=2.0 + pydantic-settings
- **HTTP 客户端**: httpx + aiohttp

### 前端
- **框架**: Vue 3.5 + TypeScript 5.7
- **构建工具**: Vite 6
- **UI组件库**: Ant Design Vue 4.2
- **路由**: vue-router 4
- **地图服务**: 高德地图 JavaScript API (@amap/amap-jsapi-loader)
- **HTTP客户端**: Axios
- **导出功能**: html2canvas + jsPDF
## 📁 项目结构

```
helloagents-trip-planner/
├── backend/                         # 后端 (Python/FastAPI/LangGraph)
│   ├── run.py                       # 启动入口
│   ├── requirements.txt             # 依赖声明
│   ├── .env.example                 # 环境变量模板
│   └── app/
│       ├── config.py                # 配置管理 (pydantic-settings)
│       ├── agents/
│       │   ├── trip_planner_agent.py   # LangGraph StateGraph (671行)
│       │   └── mcp_lifecycle.py        # MCP 生命周期管理 (131行)
│       ├── api/
│       │   ├── main.py                 # FastAPI + lifespan
│       │   └── routes/
│       │       ├── trip.py             # POST /api/trip/plan
│       │       ├── map.py              # /api/map/*
│       │       └── poi.py              # /api/poi/*
│       ├── models/
│       │   └── schemas.py             # Pydantic 数据模型
│       └── services/
│           ├── llm_service.py         # ChatOpenAI + 结构化输出
│           └── amap_service.py        # MCP 工具服务封装
├── frontend/                        # 前端 (Vue 3/TypeScript)
│   ├── package.json
│   ├── vite.config.ts               # Vite 配置 (代理 /api → :8000)
│   ├── tsconfig.json
│   └── src/
│       ├── main.ts                  # 应用入口 (路由 + Antd 注册)
│       ├── App.vue                  # 根布局
│       ├── views/
│       │   ├── Home.vue             # 首页 — 旅行表单
│       │   └── Result.vue           # 结果页 — 行程 + 地图 + 编辑 + 导出
│       ├── services/api.ts          # Axios 封装
│       └── types/index.ts           # TypeScript 类型
└── docs/                            # 文档
    ├── ARCHITECTURE.md              # 架构文档
    ├── IMAGE_SOLUTION.md            # 图片方案说明
    ├── PROJECT_ANALYSIS.md          # 项目分析报告
    └── CAREER_ADVICE.md             # 求职建议
```

## 🚀 快速开始

### 前提条件

- Python 3.11+
- Node.js 16+
- 高德地图API密钥 (Web服务API和Web端(JS API))
- LLM API密钥 (OpenAI/DeepSeek等)

### 后端安装

1. 进入后端目录
```bash
cd backend
```

2. 创建虚拟环境并安装依赖
```bash
uv venv .venv
uv pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件,填入你的API密钥
```

4. 启动后端服务
```bash
uv run uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端安装

1. 进入前端目录
```bash
cd frontend
```

2. 安装依赖
```bash
npm install
```

3. 配置环境变量
```bash
# 创建.env文件, 填入高德地图Web API Key 和 Web端JS API Key
cp .env.example .env
```

4. 启动开发服务器
```bash
npm run dev
```

5. 打开浏览器访问 `http://localhost:5173`
## 📝 使用指南

1. 在首页填写旅行信息:
   - 目的地城市
   - 旅行日期和天数
   - 交通方式偏好
   - 住宿偏好
   - 旅行风格标签

2. 点击"生成旅行计划"按钮

3. 系统将:
   - LangGraph 并行调用高德地图 MCP 工具 (景点+天气+酒店)
   - LLM 结构化输出生成完整行程计划
   - 自动获取景点真实图片 (高德 POI 详情)
   - 自动降级: 任何环节失败都有备用方案

4. 查看结果:
   - 每日详细行程
   - 景点信息与地图标记
   - 交通路线规划
   - 天气预报
   - 餐饮推荐

5. 可选操作:
   - 编辑行程 (删除/调整景点顺序)
   - 导出为 PNG 图片或 PDF 文件

## 🔧 核心实现

### LangGraph StateGraph

```python
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

# 加载 MCP 工具
client = MultiServerMCPClient({
    "amap": {
        "transport": "stdio",
        "command": "uvx", "args": ["amap-mcp-server"],
        "env": {"AMAP_MAPS_API_KEY": "your_key"}
    }
})
tools = await client.get_tools()  # 16 个高德地图工具

# 构建 LangGraph (三节点状态图)
builder = StateGraph(TripPlannerState)
builder.add_node("parallel_search", parallel_search)   # asyncio.gather 并行搜索
builder.add_node("generate_plan", generate_plan)       # structured_output 生成行程
builder.add_node("enrich_images", enrich_images)       # 获取景点真实图片
builder.add_edge(START, "parallel_search")
builder.add_edge("parallel_search", "generate_plan")
builder.add_edge("generate_plan", "enrich_images")
builder.add_edge("enrich_images", END)
graph = builder.compile()

# 执行
result = await graph.ainvoke({"trip_request": request})
```

## 📄 API文档

启动后端服务后,访问 `http://localhost:8000/docs` 查看完整的API文档。

主要端点:
- `POST /api/trip/plan` - 生成旅行计划
- `GET /api/map/poi` - 搜索POI
- `GET /api/map/weather` - 查询天气
- `POST /api/map/route` - 规划路线
- `GET /api/poi/detail/{poi_id}` - 获取POI详情

## 🤝 贡献指南

欢迎提交Pull Request或Issue!

## 📜 开源协议

CC BY-NC-SA 4.0

## 🙏 致谢

- [高德地图开放平台](https://lbs.amap.com/) - 地图服务
- [amap-mcp-server](https://github.com/sugarforever/amap-mcp-server) - 高德地图MCP服务器

---

**智能旅行助手** - 让旅行计划变得简单而智能 🌈