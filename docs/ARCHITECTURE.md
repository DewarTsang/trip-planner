# 🏗️ 智能旅行助手 — 项目架构文档

> **版本**: 2.0.0 (LangChain + LangGraph)  
> **生成日期**: 2026-07-31  

---

## 📋 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [项目结构](#3-项目结构)
4. [架构设计](#4-架构设计)
5. [后端: LangGraph 多智能体系统](#5-后端-langgraph-多智能体系统)
6. [后端: API 与路由](#6-后端-api-与路由)
7. [后端: 服务层](#7-后端-服务层)
8. [前端架构](#8-前端架构)
9. [数据模型](#9-数据模型)
10. [数据流](#10-数据流)
11. [配置管理](#11-配置管理)
12. [性能指标](#12-性能指标)
13. [已知局限与待改进项](#13-已知局限与待改进项)

---

## 1. 项目概述

智能旅行助手是一个基于 **LangChain + LangGraph** 多智能体框架的 AI 旅行规划应用。用户输入目的地、日期、偏好后，系统并发调用高德地图 MCP 工具（景点搜索、天气、酒店），再由 LLM 通过结构化输出生成包含景点、餐饮、住宿、预算和实用建议的完整旅行计划。

### 核心能力

| 能力 | 技术实现 |
|------|---------|
| 🤖 并行工具调用 | `asyncio.gather` — 景点+天气+酒店 3 路并发 |
| 🗺️ MCP 协议集成 | `langchain-mcp-adapters` + `amap-mcp-server` (16 个工具) |
| 📋 结构化输出 | `ChatOpenAI.with_structured_output(TripPlan, method="function_calling")` |
| 🛡️ 多级降级 | 工具不可用 → LLM 失败 → 备用模板计划 |
| 🎨 现代前端 | Vue 3 + TypeScript + Ant Design Vue + 高德 JS API |
| 📤 导出功能 | 行程可导出为 PNG 图片 / PDF 文件 |

---

## 2. 技术栈

### 2.1 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.11.15 | 运行环境 |
| **LangChain** | 1.3.14 | LLM 应用框架 |
| **LangChain Core** | 1.5.3 | 核心抽象 (`BaseTool`, `BaseMessage`) |
| **LangGraph** | 1.2.10 | 状态图编排引擎 |
| **LangChain OpenAI** | 1.4.1 | OpenAI 兼容的 ChatModel |
| **LangChain MCP Adapters** | 0.3.1 | MCP 协议→LangChain Tool 适配 |
| **MCP** | 1.29.0 | Model Context Protocol 核心库 |
| **FastAPI** | 0.141.1 | Web 框架 |
| **Uvicorn** | 0.52.0 | ASGI 服务器 |
| **Pydantic** | 2.13.4 | 数据校验与序列化 |
| **HTTPX** | 0.28.1 | HTTP 客户端 (MCP transport) |
| **python-dotenv** | 1.2.2 | 环境变量加载 |

### 2.2 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| **Vue** | ^3.5.13 | 渐进式 UI 框架 |
| **TypeScript** | ^5.7.3 | 类型安全 |
| **Vite** | ^6.0.7 | 构建工具 |
| **Vue Router** | ^4.5.0 | 路由管理 |
| **Ant Design Vue** | ^4.2.6 | UI 组件库 |
| **Axios** | ^1.7.9 | HTTP 请求 |
| **高德 JSAPI Loader** | ^1.0.1 | 高德地图 2.0 前端 SDK |
| **html2canvas** | ^1.4.1 | 导出图片 |
| **jsPDF** | ^3.0.3 | 导出 PDF |

### 2.3 外部服务

| 服务 | 协议 | 用途 |
|------|------|------|
| **DeepSeek API** (`api.deepseek.com`) | OpenAI 兼容 REST | LLM 推理 (`deepseek-v4-flash`) |
| **高德地图 MCP Server** (`amap-mcp-server`) | MCP (stdio) | POI 搜索、天气、路线、地理编码 |
| **高德地图 JS API v2.0** | 浏览器 SDK | 前端地图渲染、标记、路线 |
| **Unsplash API** | REST | 景点图片获取 |

---

## 3. 项目结构

```
helloagents-trip-planner/
├── README.md                              # 项目说明 (待更新)
├── docs/                                  # 文档
│   ├── ARCHITECTURE.md                    # 本文件 — 架构文档
│   ├── FRAMEWORK_COMPARISON.md            # 框架选型对比分析
│   └── CAREER_ADVICE.md                   # 求职视角建议
│
├── backend/                               # 后端 (Python/FastAPI/LangGraph)
│   ├── run.py                             # 启动入口 (16 行)
│   ├── requirements.txt                   # 依赖声明 (19 行)
│   ├── .env.example                       # 环境变量模板
│   ├── .env                               # 实际密钥 (不纳入版本控制)
│   └── app/
│       ├── __init__.py                    # 应用包 (v2.0.0)
│       ├── config.py                      # Pydantic Settings (104 行)
│       ├── agents/                        # 智能体模块
│       │   ├── __init__.py
│       │   ├── trip_planner_agent.py      # LangGraph 旅行规划图 (380 行) ⭐
│       │   └── mcp_lifecycle.py           # MCP 生命周期管理 (131 行) ⭐ 新建
│       ├── api/                           # FastAPI 接口层
│       │   ├── __init__.py
│       │   ├── main.py                    # 应用入口 + lifespan (115 行)
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── trip.py                # POST /api/trip/plan (84 行)
│       │       ├── map.py                 # /api/map/* 地图服务 (162 行)
│       │       └── poi.py                 # /api/poi/* POI+图片 (129 行)
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py                # Pydantic 数据模型 (206 行)
│       └── services/
│           ├── __init__.py
│           ├── llm_service.py             # ChatOpenAI + 结构化输出 (79 行)
│           ├── amap_service.py            # MCP 工具服务封装 (160 行)
│           └── unsplash_service.py        # Unsplash 图片服务 (86 行)
│
└── frontend/                              # 前端 (Vue 3/TypeScript)
    ├── index.html                         # HTML 入口
    ├── package.json                       # Node 依赖
    ├── tsconfig.json                      # TypeScript 配置
    ├── vite.config.ts                     # Vite 构建 + API 代理
    ├── .env.example                       # 环境变量模板
    └── src/
        ├── main.ts                        # 应用入口 — 路由 + Antd 注册 (31 行)
        ├── App.vue                        # 根组件 — 布局框架 (28 行)
        ├── views/
        │   ├── Home.vue                   # 首页 — 旅行表单 (649 行)
        │   └── Result.vue                 # 结果页 — 行程 + 地图 (1434 行)
        ├── services/
        │   └── api.ts                     # Axios 封装 (65 行)
        └── types/
            └── index.ts                   # TypeScript 类型定义 (95 行)
```

### 代码量统计

| 层级 | 文件数 | 总行数 |
|------|--------|--------|
| 后端 Python | 15 | **1,666** |
| 前端 Vue/TS | 7 | **2,302** |
| 配置文件 | 6 | ~150 |
| **合计** | **28** | **~4,100** |

---

## 4. 架构设计

### 4.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                         用户浏览器                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Vue 3 SPA (Vite :5173)                     │  │
│  │  ┌──────────┐   ┌──────────────┐   ┌────────────────────┐  │  │
│  │  │ Home.vue │──▶│ sessionStor. │──▶│ Result.vue         │  │  │
│  │  │ (表单)    │   │ tripPlan     │   │ 高德地图 JS API    │  │  │
│  │  └────┬─────┘   └──────────────┘   │ 导出 PNG/PDF       │  │  │
│  │       │                             └────────────────────┘  │  │
│  └───────┼──────────────────────────────────────────────────────┘  │
└──────────┼──────────────────────────────────────────────────────────┘
           │ Axios (120s timeout)
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                  FastAPI 服务 (Uvicorn :8000)                      │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                       lifespan                               │ │
│  │  startup → init_mcp_client()  │  shutdown → shutdown_mcp()  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐ │
│  │ /api/trip/*   │  │ /api/map/*    │  │ /api/poi/*            │ │
│  │ trip.py       │  │ map.py        │  │ poi.py               │ │
│  └───────┬───────┘  └───────┬───────┘  └───────────┬───────────┘ │
│          │                  │                      │              │
│  ┌───────▼──────────────────▼──────────────────────▼───────────┐ │
│  │                    服务层 (Singletons)                       │ │
│  │  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │ │
│  │  │ llm_service    │  │ amap_service │  │ unsplash_service│  │ │
│  │  │ ChatOpenAI     │  │ BaseTool     │  │ requests.get    │  │ │
│  │  │ +structured    │  │ .ainvoke()   │  │                 │  │ │
│  │  └───────┬────────┘  └──────┬───────┘  └─────────────────┘  │ │
│  └──────────┼──────────────────┼────────────────────────────────┘ │
│             │                  │                                   │
│  ┌──────────▼──────────────────▼────────────────────────────────┐ │
│  │               LangGraph StateGraph                            │ │
│  │                                                                │ │
│  │  ┌──────────────────────┐     ┌─────────────────────────┐    │ │
│  │  │  parallel_search     │────▶│    generate_plan        │    │ │
│  │  │  (asyncio.gather)    │     │  (with_structured_      │    │ │
│  │  │  ├─ maps_text_search │     │   output → TripPlan)    │    │ │
│  │  │  ├─ maps_weather     │     │         ↓ fallback      │    │ │
│  │  │  └─ maps_text_search │     │  _create_fallback_plan  │    │ │
│  │  └──────────────────────┘     └─────────────────────────┘    │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌──────────┐     ┌──────────────┐     ┌──────────────┐
    │ DeepSeek │     │ amap-mcp-    │     │  Unsplash    │
    │ API      │     │ server       │     │  API         │
    │(REST)    │     │ (MCP/stdio)  │     │  (REST)      │
    └──────────┘     └──────────────┘     └──────────────┘
```

### 4.2 核心设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 智能体框架 | LangGraph StateGraph | 比 SimpleAgent 链式调用更灵活，支持并行 |
| MCP 生命周期 | FastAPI lifespan 管理 | 启动一次，全请求复用；消除每次请求创建子进程开销 |
| 并行策略 | 单节点 `asyncio.gather` | 比 LangGraph `Send()` fan-out 更简单，无子状态合并问题 |
| 工具调用 | 直接 `BaseTool.ainvoke()` | 比通过 LLM 路由更快更可靠 |
| 计划生成 | `with_structured_output(method="function_calling")` | 消除脆弱的 JSON 文本正则解析 |
| LLM 兼容 | DeepSeek thinking 禁用 | `extra_body: {thinking: {type: "disabled"}}` |
| 降级策略 | 多级 fallback | 工具不可用→空结果→LLM失败→模板计划 |

---

## 5. 后端: LangGraph 多智能体系统

### 5.1 StateGraph 设计

核心是用 LangGraph 的 `StateGraph` 编排多节点状态图。

```
START → parallel_search → generate_plan → END
```

#### State 定义 (`trip_planner_agent.py:24-32`)

```python
class TripPlannerState(TypedDict, total=False):
    trip_request: TripRequest        # 用户输入
    attractions_result: str          # MCP 景点搜索结果
    weather_result: str              # MCP 天气查询结果
    hotel_result: str                # MCP 酒店搜索结果
    trip_plan: Optional[TripPlan]    # 最终输出
    errors: List[str]                # 错误累积
```

#### 节点 1: `parallel_search` (async)

- **策略**: 3 个 `async def` 内部函数，通过 `asyncio.gather(return_exceptions=True)` 并发执行
- **MCP 工具调用**:
  - `maps_text_search(keywords=<偏好>, city=<城市>)` → 景点
  - `maps_weather(city=<城市>)` → 天气
  - `maps_text_search(keywords=<住宿偏好>, city=<城市>)` → 酒店
- **容错**: 任一失败不影响其他，错误收集到 `errors` 列表
- **MCP 不可用**: 捕获 `RuntimeError`，返回空结果 + 错误信息，不阻断图执行
- **实测耗时**: ~0.8 秒（3 路并发）

#### 节点 2: `generate_plan` (async)

- **LLM 调用**: `get_planner_llm().ainvoke(prompt)` 
- **结构化输出**: `with_structured_output(TripPlan, method="function_calling")` — 直接返回 Pydantic 对象
- **Prompt**: `_build_planner_query()` 组装中文 prompt，包含景点/天气/酒店原始数据
- **降级**: LLM 调用失败时 → `_create_fallback_plan(request)` 生成模板计划
- **实测耗时**: ~17.5 秒（DeepSeek 推理 + 结构化输出）

#### Fallback 计划 (`_create_fallback_plan`)

当 LLM 不可用时，生成包含占位景点/餐饮/酒店的模板行程：
- 每天 2 个模板景点 + 3 餐
- 含基础预算汇总
- 明确标注"备用计划"和实用建议

### 5.2 MCP 生命周期 (`mcp_lifecycle.py` ⭐ 新建)

```python
# 应用启动时 (FastAPI lifespan)
await init_mcp_client()
  ├── MultiServerMCPClient({
  │     "amap": {
  │       "transport": "stdio",         # 子进程通信
  │       "command": "uvx",            # Python 包运行器
  │       "args": ["amap-mcp-server"],
  │       "env": {"AMAP_MAPS_API_KEY": "..."}
  │     }
  │   })
  └── await client.get_tools()  →  16 个 LangChain BaseTool

# 请求时
get_amap_tools()  →  List[BaseTool]  (单例)

# 应用关闭时
await shutdown_mcp_client()  (子进程 GC 清理)
```

**可用的 16 个 MCP 工具**: `maps_regeocode`, `maps_geo`, `maps_ip_location`, `maps_weather`, `maps_bicycling_by_address`, `maps_bicycling_by_coordinates`, `maps_direction_walking_by_address`, `maps_direction_walking_by_coordinates`, `maps_direction_driving_by_address`, `maps_direction_driving_by_coordinates`, `maps_direction_transit_integrated_by_address`, `maps_direction_transit_integrated_by_coordinates`, `maps_distance`, `maps_text_search`, `maps_around_search`, `maps_search_detail`

### 5.3 LLM 服务 (`llm_service.py`)

```python
# 通用聊天模型 (temperature=0.7)
get_chat_model() → ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://api.deepseek.com",
)

# 规划专用模型 (temperature=0.2, 禁用 thinking, 结构化输出)
get_planner_llm() → ChatOpenAI(
    model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}}
).with_structured_output(TripPlan, method="function_calling")
```

**DeepSeek 兼容性说明**: DeepSeek v4-flash 的 thinking 模式与 `function_calling` / `tool_choice` 冲突，须通过 `extra_body` 显式禁用。该参数被 OpenAI 忽略，不影响跨供应商切换。

---

## 6. 后端: API 与路由

### 6.1 路由总览

| 方法 | 端点 | 文件 | 行数 | 说明 |
|------|------|------|------|------|
| `GET` | `/` | `main.py` | — | 服务信息 (含 framework 字段) |
| `GET` | `/health` | `main.py` | — | 全局健康检查 + MCP 工具数 |
| `POST` | `/api/trip/plan` | `trip.py` | 84 | **核心**: 生成旅行计划 |
| `GET` | `/api/trip/health` | `trip.py` | — | 规划服务健康检查 |
| `GET` | `/api/map/poi` | `map.py` | 162 | POI 搜索 |
| `GET` | `/api/map/weather` | `map.py` | — | 天气查询 |
| `POST` | `/api/map/route` | `map.py` | — | 路线规划 |
| `GET` | `/api/map/health` | `map.py` | — | 地图服务健康检查 |
| `GET` | `/api/poi/search` | `poi.py` | 129 | POI 搜索 (简版) |
| `GET` | `/api/poi/detail/{id}` | `poi.py` | — | POI 详情 |
| `GET` | `/api/poi/photo` | `poi.py` | — | Unsplash 景点图片 |

### 6.2 核心接口: `POST /api/trip/plan`

**请求体** (`TripRequest`):
```json
{
  "city": "杭州",
  "start_date": "2025-08-15",
  "end_date": "2025-08-17",
  "travel_days": 3,
  "transportation": "公共交通",
  "accommodation": "经济型酒店",
  "preferences": ["自然风光", "历史文化"],
  "free_text_input": "想去西湖和灵隐寺"
}
```

**响应体** (`TripPlanResponse`):
```json
{
  "success": true,
  "message": "旅行计划生成成功",
  "data": {
    "city": "杭州",
    "start_date": "2025-08-15",
    "end_date": "2025-08-17",
    "days": [
      {
        "date": "2025-08-15",
        "day_index": 0,
        "description": "第一天游览西湖核心景区...",
        "hotel": { "name": "可见时光·望达斯旅舍", "price_range": "150-250元/晚", "rating": "4.2" },
        "attractions": [
          { "name": "杭州西湖风景名胜区-湖滨公园", "location": {"longitude": 120.161, "latitude": 30.258}, "ticket_price": 0 }
        ],
        "meals": [
          { "type": "breakfast", "name": "新丰小吃(延安路店)", "estimated_cost": 25 }
        ]
      }
    ],
    "weather_info": [...],
    "budget": { "total": 905, "total_attractions": 0, "total_hotels": 400, "total_meals": 445, "total_transportation": 60 },
    "overall_suggestions": "杭州8月天气炎热，建议做好防晒措施..."
  }
}
```

**超时设计**: 前端 Axios 120 秒，后端无显式超时（LLM 推理 + MCP 调用通常 <30 秒）。

---

## 7. 后端: 服务层

### 7.1 `amap_service.py` — 高德 MCP 工具封装

封装了 5 个 MCP 工具的直接调用：

| 方法 | MCP 工具 | 返回 | 解析状态 |
|------|---------|------|---------|
| `search_poi()` | `maps_text_search` | `List[POIInfo]` | ⚠️ TODO: 返回 `[]` |
| `get_weather()` | `maps_weather` | `List[WeatherInfo]` | ⚠️ TODO: 返回 `[]` |
| `plan_route()` | `maps_direction_*_by_address` | `Dict` | ⚠️ TODO: 返回 `{}` |
| `geocode()` | `maps_geo` | `Optional[Location]` | ⚠️ TODO: 返回 `None` |
| `get_poi_detail()` | `maps_search_detail` | `Dict` | ✅ 含 JSON 正则提取 |

> **注意**: 前 4 个方法的返回值为空——MCP 工具确实被调用了，但返回的字符串未被解析为结构化数据。旅行规划使用的是 LangGraph 节点中直接调用工具拿到的**原始字符串**，传给 LLM 由 LLM 自行理解和提取信息。`/api/map/*` 和 `/api/poi/*` 路由直接调用这些方法，所以独立使用时返回空数据。

### 7.2 `unsplash_service.py` — 图片服务

- 同步 `requests.get` (10s 超时)
- `search_photos(query, per_page)` → `List[dict]`
- `get_photo_url(query)` → `Optional[str]`
- 前端 `Result.vue` 在 `loadAttractionPhotos()` 中按景点名称逐张请求

### 7.3 单例模式

所有服务使用模块级全局变量实现单例：

| 服务 | 单例函数 | 全局变量 |
|------|---------|---------|
| LLM | `get_chat_model()` | `_chat_model_instance` |
| MCP 工具 | `get_amap_tools()` | `_amap_tools` |
| AmapService | `get_amap_service()` | `_amap_service` |
| UnsplashService | `get_unsplash_service()` | `_unsplash_service` |
| MultiAgentTripPlanner | `get_trip_planner_agent()` | `_multi_agent_planner` |

---

## 8. 前端架构

### 8.1 路由

```
/ (Home)  ──→  填写表单  ──→  POST /api/trip/plan  (120s 超时)
                              │
                              ▼
                   sessionStorage['tripPlan']
                              │
                              ▼
/result (Result) ←──  展示 + 地图 + 编辑 + 导出
```

### 8.2 组件树

```
App.vue
├── a-layout-header ("🌍 智能旅行助手")
└── a-layout-content
    └── <router-view />
        ├── Home.vue (649 行)
        │   ├── 背景装饰 (CSS 浮动圆圈动画)
        │   ├── 页面标题 (✈️ 智能旅行助手)
        │   └── a-card 表单
        │       ├── 📍 目的地与日期 (Input + DatePicker + 自动天数计算)
        │       ├── ⚙️ 偏好设置 (Select + CheckboxGroup)
        │       ├── 💬 额外要求 (Textarea)
        │       └── 🚀 提交按钮 + 模拟进度条
        │
        └── Result.vue (1434 行)
            ├── 页面头部 (返回/编辑/导出下拉)
            ├── 侧边导航 (a-affix + a-menu 锚点)
            └── 主内容区
                ├── 📋 行程概览
                ├── 💰 预算明细 (4 项 + 总计)
                ├── 📍 景点地图 (高德 JS API 2.0: Marker + InfoWindow + Polyline)
                ├── 📅 每日行程 (a-collapse 折叠面板)
                │   ├── 🎯 景点卡片 (Unsplash 图片/SVG 占位 + 编辑模式)
                │   ├── 🏨 酒店推荐 (a-descriptions)
                │   └── 🍽️ 餐饮安排
                └── 🌤️ 天气信息 (3 列网格)
```

### 8.3 关键前端功能

| 功能 | 实现方式 |
|------|---------|
| **自动天数计算** | `watch` 监听 start_date/end_date → `end.diff(start, 'day') + 1` |
| **进度模拟** | `setInterval` 渐进式 0→90%，分阶段显示搜索/天气/酒店/规划状态 |
| **编辑模式** | 景点增删、顺序调整 (`moveAttraction`)、字段编辑，保存后重建地图 |
| **导出 PNG** | html2canvas 克隆 DOM → 处理 Ant Design 样式 → Canvas → download |
| **导出 PDF** | jsPDF + html2canvas → A4 自动分页 |
| **地图可视化** | 高德 JS API 2.0: Marker (编号标签) + InfoWindow + Polyline (天路线) + setFitView |
| **景点图片** | Unsplash API (/api/poi/photo) → 失败降级为 SVG 渐变占位图 |
| **侧边导航** | a-affix 固定 + 点击 scrollIntoView 平滑滚动 |

---

## 9. 数据模型

完整的 Pydantic v2 模型层次 (`models/schemas.py`, 206 行):

```
TripRequest
├── city: str
├── start_date: str (YYYY-MM-DD)
├── end_date: str
├── travel_days: int (1-30)
├── transportation: str
├── accommodation: str
├── preferences: List[str]
└── free_text_input: Optional[str]

TripPlan (核心输出)
├── city: str
├── start_date: str
├── end_date: str
├── days: List[DayPlan]
│   ├── date, day_index, description
│   ├── transportation, accommodation
│   ├── hotel: Optional[Hotel]
│   │   └── name, address, location, price_range, rating, distance, type, estimated_cost
│   ├── attractions: List[Attraction]
│   │   └── name, address, location: Location{lon, lat}, visit_duration, description,
│   │       category, rating, photos, poi_id, image_url, ticket_price
│   └── meals: List[Meal]
│       └── type(breakfast/lunch/dinner/snack), name, address, location, description, estimated_cost
├── weather_info: List[WeatherInfo]
│   └── date, day_weather, night_weather, day_temp, night_temp, wind_direction, wind_power
│       (含 @field_validator 自动剥离 °C/℃ 单位)
├── overall_suggestions: str
└── budget: Optional[Budget]
    └── total_attractions, total_hotels, total_meals, total_transportation, total

TripPlanResponse
├── success: bool
├── message: str
└── data: Optional[TripPlan]
```

---

## 10. 数据流

### 10.1 请求-响应完整流程

```
用户填写表单 → Home.vue: handleSubmit()
    │
    ├─ 日期校验 (结束≥开始, ≤30天)
    ├─ 启动进度条模拟 (setInterval 500ms)
    │
    ▼
api.ts: generateTripPlan(formData)
    │  POST /api/trip/plan  (JSON body: TripRequest, timeout: 120s)
    ▼
FastAPI (trip.py): plan_trip()
    │
    ├─ get_trip_planner_agent()  → 单例 (首次调用时编译 StateGraph)
    └─ await agent.plan_trip(request)
        │
        ▼
    LangGraph StateGraph.ainvoke(state)
        │
        ├─ [Node 1] parallel_search (asyncio.gather, ~0.8s)
        │   ├─ maps_text_search(偏好, 城市) → 景点原始 JSON 字符串
        │   ├─ maps_weather(城市)           → 天气原始 JSON 字符串
        │   └─ maps_text_search(住宿, 城市) → 酒店原始 JSON 字符串
        │
        └─ [Node 2] generate_plan (~17.5s)
            ├─ _build_planner_query() → 中文 prompt
            ├─ get_planner_llm().ainvoke(prompt)
            │   └─ with_structured_output(TripPlan, function_calling)
            │       └─ DeepSeek API (thinking=disabled)
            │           └─ 返回 TripPlan Pydantic 对象
            └─ 失败 → _create_fallback_plan(request)
                │
                ▼
    TripPlanResponse { success: true, data: TripPlan }
        │
        ▼
Home.vue: 接收响应
    ├─ sessionStorage.setItem('tripPlan', JSON)
    └─ router.push('/result')
        │
        ▼
Result.vue: onMounted()
    ├─ 读取 sessionStorage
    ├─ loadAttractionPhotos() → GET /api/poi/photo (Unsplash)
    └─ initMap() → 高德 JS API 2.0 (Marker + Polyline + InfoWindow)
```

### 10.2 降级路径

```
MCP 工具不可用?
  ├─ YES → parallel_search 返回空结果 + error
  └─ NO  → 正常调用

LLM 结构化输出成功?
  ├─ YES → 返回真实 TripPlan ✅
  └─ NO  → _create_fallback_plan() → 模板 TripPlan ⚠️

整个 Graph 执行失败?
  └─ YES → plan_trip() 捕获异常 → _create_fallback_plan()
```

---

## 11. 配置管理

### 11.1 环境变量

| 变量 | 用途 | 必填 |
|------|------|:---:|
| `LLM_MODEL_ID` | 模型名称 (如 `deepseek-v4-flash`) | ✅ |
| `LLM_API_KEY` | LLM API 密钥 | ✅ |
| `LLM_BASE_URL` | LLM API 地址 | ✅ |
| `LLM_TIMEOUT` | LLM 请求超时 (秒) | — |
| `AMAP_API_KEY` | 高德地图 Web 服务 API Key | ✅ |
| `UNSPLASH_ACCESS_KEY` | Unsplash Access Key | — |
| `UNSPLASH_SECRET_KEY` | Unsplash Secret Key | — |
| `HOST` | 服务器绑定地址 (默认 `0.0.0.0`) | — |
| `PORT` | 服务器端口 (默认 `8000`) | — |
| `CORS_ORIGINS` | 允许的跨域来源 | — |
| `LOG_LEVEL` | 日志级别 (默认 `INFO`) | — |

### 11.2 配置加载机制

```
.env 文件
    ↓ load_dotenv()
os.environ
    ↓ os.getenv()              ← LLM 配置 (llm_service.py)
    ↓ Pydantic Settings        ← AMAP/Unsplash/服务器配置 (config.py)
```

LLM 配置通过 `os.getenv()` 直接读取而非 Pydantic Settings，原因是 `config.py` 中 `Settings` 类设置了 `extra = "ignore"`，`LLM_API_KEY` 等未声明的字段会被忽略。

---

## 12. 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| MCP 工具加载 | ~3s | 应用启动时一次性，16 个子进程工具 |
| 并行搜索 (3 路 MCP) | **~0.8s** | 景点 + 天气 + 酒店并发 |
| LLM 规划生成 | **~17.5s** | DeepSeek v4-flash 推理 + 结构化输出 |
| **端到端总耗时** | **~18.3s** | MCP 搜索 + LLM 规划 |
| Fallback 降级 | <0.1s | 无任何网络调用 |
| 前端超时 | 120s | Axios 配置，留有充足余量 |

---

## 13. 已知局限与待改进项

### 13.1 功能局限

| 问题 | 影响 | 建议 |
|------|------|------|
| **MCP 结果未解析** | `amap_service.py` 的 `search_poi`/`get_weather`/`plan_route`/`geocode` 返回空值 | 解析 MCP JSON 字符串为 Pydantic 模型 |
| **无数据库持久化** | 行程仅存 `sessionStorage`，刷新丢失 | 引入 SQLite/PostgreSQL + 用户系统 |
| **无用户认证** | 无登录/注册 | 添加 JWT/OAuth |
| **无自动化测试** | 回归风险 | 添加 pytest + pytest-asyncio |
| **MCP shutdown 为空操作** | `langchain-mcp-adapters` 0.3.1 无 close API | 升级后添加显式清理 |
| **前端硬编码后端地址** | `Result.vue:435` 直接 `fetch('http://localhost:8000/...')` | 使用 Vite 代理或环境变量 |

### 13.2 架构优化

| 优化项 | 预期收益 |
|--------|---------|
| 流式 SSE 输出 | 用户体验: 实时看到行程逐字生成 |
| LangSmith 可观测性 | 调试: 追踪每次 Tool Call 和 LLM 推理 |
| LLM 结果缓存 | 相同 query 24h 内复用，降低 API 费用 |
| `amap_service.py` 结果解析 | 让 `/api/map/*` 和 `/api/poi/*` 路由返回有效数据 |

---

## 附录

### A. 迁移历史

| 版本 | 框架 | 主要变更 |
|------|------|---------|
| **v2.0.0** | **LangChain 1.3 + LangGraph 1.2** | StateGraph 并行，`function_calling` 结构化输出，MCP 生命周期管理 |


### B. 启动命令

```bash
# 后端
cd backend
uv venv .venv
uv pip install -r requirements.txt
cp .env.example .env  # 编辑填入真实密钥
uv run uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
cp .env.example .env  # 编辑填入高德 JS API Key
npm run dev            # → http://localhost:5173
```

### C. 许可

CC BY-NC-SA 4.0
