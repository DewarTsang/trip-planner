"""LangGraph多智能体旅行规划系统

基于LangGraph StateGraph编排:
1. 并行搜索: 景点 + 天气 + 酒店 (asyncio.gather, 直接调用MCP工具)
2. 行程生成: LLM with_structured_output → TripPlan (or fallback)
3. POI图片: 高德maps_search_detail → 真实景点照片
"""

import asyncio
import ast
import json
import re
from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from ..models.schemas import (
    TripRequest, TripPlan, DayPlan,
    Attraction, Meal, WeatherInfo, Location, Hotel, Budget
)
from ..services.llm_service import get_planner_llm, get_chat_model
from .mcp_lifecycle import get_amap_tools, _find_tool_by_name


# ============ State 定义 ============

class TripPlannerState(TypedDict, total=False):
    """LangGraph状态 — 在节点间传递的数据"""
    trip_request: TripRequest
    attractions_result: str
    weather_result: str
    hotel_result: str
    poi_data: str                       # JSON: [{"id","name","address"},...] 解析后的POI列表
    trip_plan: Optional[TripPlan]
    errors: List[str]


# ============ MCP 工具响应解析 ============

def _parse_mcp_response(raw: str) -> Optional[dict]:
    """解析 MCP 工具返回的 Python 列表字符串 → JSON dict

    MCP tools return: [{'type': 'text', 'text': '{"key": "value", ...}'}]
    """
    if not raw:
        return None
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and item.get("type") == "text":
                    return json.loads(item["text"])
        return None
    except (ValueError, SyntaxError, json.JSONDecodeError):
        return None


def _parse_mcp_pois(raw_result: str) -> List[dict]:
    """从 MCP text_search 响应中提取 POI 列表

    Returns: [{"id": "B023B13L9M", "name": "杭州西湖", "address": "龙井路1号"}, ...]
    """
    data = _parse_mcp_response(raw_result)
    if not data:
        return []
    pois = data.get("pois", [])
    return [
        {"id": p.get("id", ""), "name": p.get("name", ""), "address": p.get("address", "")}
        for p in pois if p.get("id") and p.get("name")
    ]


def _parse_mcp_weather(raw_result: str) -> List[dict]:
    """从 MCP weather 响应中提取天气预报

    Returns: [{"date": "2026-07-31", "day_weather": "晴", ...}, ...]
    """
    data = _parse_mcp_response(raw_result)
    if not data:
        return []
    return data.get("forecasts", [])


# ============ 图节点 ============

async def _parallel_search_node(state: TripPlannerState) -> Dict[str, Any]:
    """并行搜索节点: 同时调用景点/天气/酒店三个MCP工具

    使用 asyncio.gather 并发执行三个独立搜索，任一失败不影响其他。
    MCP工具未初始化时降级返回空结果。
    同时解析POI数据供后续图片获取使用。
    """
    req = state["trip_request"]

    try:
        tools = get_amap_tools()
    except RuntimeError as e:
        print(f"  ⚠️  MCP工具不可用: {e}")
        return {
            "attractions_result": "", "weather_result": "", "hotel_result": "",
            "poi_data": "[]",
            "errors": [f"MCP工具不可用: {e}"],
        }

    async def _search_attractions() -> str:
        tool = _find_tool_by_name(tools, "maps_text_search")
        keywords = req.preferences[0] if req.preferences else "景点"
        result = await tool.ainvoke({
            "keywords": f"{keywords}",
            "city": req.city,
            "citylimit": "true"
        })
        return str(result)

    async def _search_weather() -> str:
        tool = _find_tool_by_name(tools, "maps_weather")
        result = await tool.ainvoke({"city": req.city})
        return str(result)

    async def _search_hotel() -> str:
        tool = _find_tool_by_name(tools, "maps_text_search")
        result = await tool.ainvoke({
            "keywords": req.accommodation,
            "city": req.city,
            "citylimit": "true"
        })
        return str(result)

    print("  🔄 并行搜索景点/天气/酒店...")
    t1 = datetime.now()

    results = await asyncio.gather(
        _search_attractions(),
        _search_weather(),
        _search_hotel(),
        return_exceptions=True
    )

    elapsed = (datetime.now() - t1).total_seconds()
    print(f"  ✅ 并行搜索完成 (耗时 {elapsed:.1f}s)")

    errors = []
    attractions_result = ""
    weather_result = ""
    hotel_result = ""
    all_pois: List[dict] = []

    if isinstance(results[0], Exception):
        errors.append(f"景点搜索失败: {results[0]}")
        print(f"  ❌ 景点搜索失败: {results[0]}")
    else:
        attractions_result = results[0]
        pois = _parse_mcp_pois(attractions_result)
        all_pois.extend(pois)
        print(f"  📍 景点搜索: {len(pois)} 个POI")

    if isinstance(results[1], Exception):
        errors.append(f"天气查询失败: {results[1]}")
        print(f"  ❌ 天气查询失败: {results[1]}")
    else:
        weather_result = results[1]
        forecasts = _parse_mcp_weather(weather_result)
        print(f"  🌤️  天气查询: {len(forecasts)} 天预报")

    if isinstance(results[2], Exception):
        errors.append(f"酒店搜索失败: {results[2]}")
        print(f"  ❌ 酒店搜索失败: {results[2]}")
    else:
        hotel_result = results[2]
        hotel_pois = _parse_mcp_pois(hotel_result)
        all_pois.extend(hotel_pois)
        print(f"  🏨 酒店搜索: {len(hotel_pois)} 个POI")

    return {
        "attractions_result": attractions_result,
        "weather_result": weather_result,
        "hotel_result": hotel_result,
        "poi_data": json.dumps(all_pois, ensure_ascii=False),
        "errors": errors,
    }


async def _generate_plan_node(state: TripPlannerState) -> Dict[str, Any]:
    """行程生成节点: 用LLM结构化输出生成TripPlan

    成功: 返回 with_structured_output 解析的TripPlan
    失败: 重试一次后仍失败则返回 fallback 计划
    """
    req = state["trip_request"]

    print("  📋 正在生成行程计划...")
    t1 = datetime.now()

    planner_llm = get_planner_llm()
    query = _build_planner_query(
        req,
        state.get("attractions_result", ""),
        state.get("weather_result", ""),
        state.get("hotel_result", ""),
    )

    last_error = None
    for attempt in range(2):
        try:
            trip_plan = await planner_llm.ainvoke(query)

            elapsed = (datetime.now() - t1).total_seconds()
            print(f"  ✅ 行程计划生成成功 (耗时 {elapsed:.1f}s)")
            print(f"   城市: {trip_plan.city}")
            print(f"   天数: {len(trip_plan.days)} 天")
            if trip_plan.budget:
                print(f"   预估总费用: ¥{trip_plan.budget.total}")

            return {"trip_plan": trip_plan}

        except Exception as e:
            last_error = e
            elapsed = (datetime.now() - t1).total_seconds()

            if attempt == 0:
                error_hint = str(e)[:200]
                print(f"  ⚠️  第1次尝试失败 (耗时 {elapsed:.1f}s): {error_hint}")
                print(f"  🔄 重试 (添加严格格式约束)...")
                type_hints = _extract_failing_types(str(e))
                query = query + "\n\n" + _build_format_correction_prompt(
                    type_hints, req.travel_days
                )
            else:
                print(f"  ⚠️  第2次尝试也失败了 (耗时 {elapsed:.1f}s): {last_error}")
                print(f"   使用备用方案生成计划...")
                break

    fallback_plan = _create_fallback_plan(req)
    return {
        "trip_plan": fallback_plan,
        "errors": state.get("errors", []) + [f"LLM规划失败(已使用备用计划): {last_error}"]
    }


async def _enrich_images_node(state: TripPlannerState) -> Dict[str, Any]:
    """POI图片丰富节点: 匹配TripPlan中的景点→高德POI→获取真实照片

    在 generate_plan 之后运行。优先通过高德REST API直接获取POI图片
    （amap-mcp-server 的 maps_search_detail 不返回 photos 字段），
    填充到 Attraction.image_url 和 Attraction.photos 字段。
    匹配失败或无图片时静默跳过，不影响主流程。
    """
    trip_plan = state.get("trip_plan")
    if not trip_plan:
        return {}

    # 解析 POI 数据
    poi_data = state.get("poi_data", "[]")
    try:
        poi_list = json.loads(poi_data)
    except json.JSONDecodeError:
        poi_list = []

    if not poi_list:
        print("  🖼️  无POI数据，跳过图片获取")
        return {}

    # 收集所有景点
    all_attractions = []
    for day in trip_plan.days:
        all_attractions.extend(day.attractions)

    print(f"  🖼️  正在获取景点图片 ({len(all_attractions)} 个景点, {len(poi_list)} 个POI)...")
    t1 = datetime.now()

    # 获取高德 API Key (用于直接调用 REST API)
    from ..config import get_settings
    settings = get_settings()
    amap_key = settings.amap_api_key

    # 并发限制
    sem = asyncio.Semaphore(5)

    async def _fetch_one(attraction: Attraction):
        async with sem:
            poi = _fuzzy_match_poi(attraction.name, poi_list)
            if not poi:
                return
            try:
                # 直接调用高德 REST API (MCP工具不返回photos)
                photo_url = await _fetch_photo_via_amap_http(poi["id"], amap_key)
                if photo_url:
                    attraction.image_url = photo_url
                    attraction.photos = [photo_url]
                    print(f"    📷 {attraction.name} → {photo_url[:80]}...")
                else:
                    print(f"    ⚪ {attraction.name} → POI无图片")
            except Exception as e:
                print(f"    ⚠️  {attraction.name}: {e}")

    await asyncio.gather(*[_fetch_one(a) for a in all_attractions])

    elapsed = (datetime.now() - t1).total_seconds()
    enriched = sum(1 for a in all_attractions if a.image_url)
    print(f"  ✅ 图片获取完成 (耗时 {elapsed:.1f}s, {enriched}/{len(all_attractions)} 个有图)")

    return {"trip_plan": trip_plan}


async def _fetch_photo_via_amap_http(poi_id: str, api_key: str) -> Optional[str]:
    """直接调用高德REST API获取POI图片

    amap-mcp-server 的 maps_search_detail 不返回 photos 字段，
    因此通过 httpx 直接调用高德 Web API 的 place/detail 接口。
    """
    import httpx

    url = "https://restapi.amap.com/v3/place/detail"
    params = {
        "key": api_key,
        "id": poi_id,
        "extensions": "all",  # 返回 photos 等详细信息
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "1":
                pois = data.get("pois", [])
                if pois and isinstance(pois, list):
                    photos = pois[0].get("photos", [])
                    if photos and isinstance(photos, list):
                        first = photos[0]
                        if isinstance(first, dict):
                            url = first.get("url")
                            if url:
                                # 高德返回小图 URL，替换为较大尺寸
                                return url
    except Exception as e:
        print(f"      HTTP请求失败: {e}")

    return None


# ============ 图片匹配辅助函数 ============

def _fuzzy_match_poi(attraction_name: str, poi_list: List[dict]) -> Optional[dict]:
    """模糊匹配景点名到POI记录"""
    # 移除常见后缀，提高匹配率
    clean_name = attraction_name.strip()
    for suffix in ["风景区", "景区", "公园", "博物馆", "寺", "庙", "塔", "湖", "山"]:
        # 不轻易移除——保留原始名称做精确匹配
        pass

    # 1. 精确匹配
    for poi in poi_list:
        if poi["name"] == clean_name:
            return poi

    # 2. 包含匹配
    for poi in poi_list:
        if clean_name in poi["name"] or poi["name"] in clean_name:
            return poi

    # 3. 移除常见关键词后的包含匹配
    simplified = clean_name
    for word in ["杭州", "北京", "上海", "南京", "西安", "成都", "重庆", "广州", "深圳",
                 "风景名胜区", "风景区", "旅游区", "游览区"]:
        simplified = simplified.replace(word, "")
    if len(simplified) >= 2:
        for poi in poi_list:
            if simplified in poi["name"] or poi["name"] in simplified:
                return poi

    # 4. 序列相似度匹配 (阈值 0.6)
    best_score = 0.6
    best_poi = None
    for poi in poi_list:
        score = SequenceMatcher(None, clean_name, poi["name"]).ratio()
        if score > best_score:
            best_score = score
            best_poi = poi

    return best_poi


def _extract_photo_url(raw_result: str) -> Optional[str]:
    """从 maps_search_detail 返回中提取第一张图片URL

    高德POI详情API返回格式:
    {"status":"1","pois":[{"photos":[{"url":"https://..."}]}]}
    """
    # 先尝试 JSON 解析
    data = _parse_mcp_response(raw_result)
    if data:
        return _navigate_photos(data)

    # 回退: 正则提取
    m = re.search(r'\{.*\}', raw_result, re.DOTALL)
    if m:
        try:
            return _navigate_photos(json.loads(m.group()))
        except json.JSONDecodeError:
            pass

    return None


def _navigate_photos(data: dict) -> Optional[str]:
    """从高德API响应结构中提取第一张图片URL"""
    if not isinstance(data, dict):
        return None
    status = data.get("status")
    if status != "1" and status != 1:
        return None
    pois = data.get("pois", [])
    if pois and isinstance(pois, list):
        photos = pois[0].get("photos", [])
        if photos and isinstance(photos, list):
            first = photos[0]
            if isinstance(first, dict):
                url = first.get("url")
                if url:
                    # 高德返回小图，尝试替换为大图
                    return url
    return None


# ============ 错误处理辅助函数 ============

def _extract_failing_types(error_str: str) -> list[str]:
    """从 Pydantic 校验错误中提取类型错误的字段名"""
    fields = set()
    for m in re.finditer(r'(\w+)\.(\w+)', error_str):
        fields.add(m.group(2))
    for m in re.finditer(r'^(\w+)\s*\n\s*Input should be', error_str, re.MULTILINE):
        fields.add(m.group(1))
    return list(fields)


def _build_format_correction_prompt(failing_fields: list[str], travel_days: int) -> str:
    """构建格式纠正提示，强调容易出错的字段"""
    hints = [f"【重要格式要求 — 上次返回数据格式错误，请严格遵循】"]

    if "days" in failing_fields:
        hints.append(
            f'- "days" 必须是一个 **数组(list)**，包含恰好 {travel_days} 个 DayPlan 对象。'
            f'  绝对不能写成纯数字 (如 days: {travel_days})！'
        )
    if "rating" in failing_fields:
        hints.append('- "rating" 字段必须是字符串，如 "4.5"、"" (不能是数字 4.5)')

    hints.append("- 所有经纬度必须是真实坐标")
    hints.append("- 所有日期格式必须为 YYYY-MM-DD")
    hints.append(f"- weather_info 数组必须包含恰好 {travel_days} 天的天气信息")
    return "\n".join(hints)


# ============ MultiAgentTripPlanner ============

class MultiAgentTripPlanner:
    """LangGraph多智能体旅行规划系统"""

    def __init__(self):
        """初始化LangGraph StateGraph"""
        print("🔄 正在构建LangGraph旅行规划图...")

        builder = StateGraph(TripPlannerState)

        builder.add_node("parallel_search", _parallel_search_node)
        builder.add_node("generate_plan", _generate_plan_node)
        builder.add_node("enrich_images", _enrich_images_node)

        # START → parallel_search → generate_plan → enrich_images → END
        builder.add_edge(START, "parallel_search")
        builder.add_edge("parallel_search", "generate_plan")
        builder.add_edge("generate_plan", "enrich_images")
        builder.add_edge("enrich_images", END)

        self.graph: CompiledStateGraph = builder.compile()

        print(f"✅ LangGraph旅行规划图构建完成")
        print(f"   节点: parallel_search → generate_plan → enrich_images")
        print(f"   搜索策略: asyncio.gather 并行")
        print(f"   输出策略: with_structured_output(TripPlan)")
        print(f"   图片策略: 高德POI详情 → 真实景点照片")

    async def plan_trip(self, request: TripRequest) -> TripPlan:
        """执行旅行规划 (async)"""
        print(f"\n{'='*60}")
        print(f"🚀 开始LangGraph旅行规划...")
        print(f"   目的地: {request.city}")
        print(f"   日期: {request.start_date} 至 {request.end_date}")
        print(f"   天数: {request.travel_days}天")
        print(f"   偏好: {', '.join(request.preferences) if request.preferences else '无'}")
        print(f"{'='*60}\n")

        t_start = datetime.now()

        try:
            result = await self.graph.ainvoke({
                "trip_request": request,
                "attractions_result": "",
                "weather_result": "",
                "hotel_result": "",
                "poi_data": "[]",
                "trip_plan": None,
                "errors": [],
            })

            trip_plan = result.get("trip_plan")
            errors = result.get("errors", [])

            if errors:
                print(f"\n⚠️  规划过程中出现 {len(errors)} 个错误:")
                for err in errors:
                    print(f"    - {err}")

            # 统计图片
            if trip_plan:
                total = sum(len(d.attractions) for d in trip_plan.days)
                with_img = sum(
                    1 for d in trip_plan.days for a in d.attractions if a.image_url
                )
                print(f"  🖼️  景点图片: {with_img}/{total}")

            elapsed = (datetime.now() - t_start).total_seconds()
            print(f"\n{'='*60}")
            print(f"✅ 旅行规划完成! 总耗时: {elapsed:.1f}s")
            print(f"{'='*60}\n")

            return trip_plan if trip_plan else _create_fallback_plan(request)

        except Exception as e:
            print(f"❌ LangGraph执行失败: {e}")
            import traceback
            traceback.print_exc()
            return _create_fallback_plan(request)


# ============ 辅助函数 ============

def _build_planner_query(
    request: TripRequest,
    attractions: str,
    weather: str,
    hotels: str = ""
) -> str:
    """构建行程规划prompt — 包含严格的格式约束"""
    query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

基本信息:
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

景点信息:
{attractions if attractions else '暂无景点数据'}

天气信息:
{weather if weather else '暂无天气数据'}

酒店信息:
{hotels if hotels else '暂无酒店数据'}

要求:
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐(breakfast, lunch, dinner)
3. 每天推荐一个具体的酒店
4. 考虑景点之间的距离和交通方式
5. 景点的经纬度坐标要真实准确
6. 必须包含预算信息(budget),汇总景点门票、酒店、餐饮、交通费用
7. weather_info数组必须包含每一天的天气信息

【严格格式约束 - 违反将导致解析失败】:
- "days" 必须是包含{request.travel_days}个DayPlan对象的数组(list)，绝对不能写成数字(如days: {request.travel_days})！
- hotel.rating 必须是字符串，如"4.5"而不是4.5
- 所有日期格式为YYYY-MM-DD，使用真实经纬度坐标
"""
    if request.free_text_input:
        query += f"\n额外要求: {request.free_text_input}"

    return query


def _create_fallback_plan(request: TripRequest) -> TripPlan:
    """创建备用计划(当LLM失败时使用)"""
    start_date = datetime.strptime(request.start_date, "%Y-%m-%d")

    days = []
    for i in range(request.travel_days):
        current_date = start_date + timedelta(days=i)

        day_plan = DayPlan(
            date=current_date.strftime("%Y-%m-%d"),
            day_index=i,
            description=f"第{i+1}天: 探索{request.city}的精彩之处",
            transportation=request.transportation,
            accommodation=request.accommodation,
            hotel=Hotel(
                name=f"{request.city}{request.accommodation}",
                address=f"{request.city}市中心区域",
                location=Location(longitude=116.4 + i * 0.01, latitude=39.9 + i * 0.01),
                price_range="300-500元",
                rating="4.5",
                distance="市中心",
                type=request.accommodation,
                estimated_cost=400
            ),
            attractions=[
                Attraction(
                    name=f"{request.city}推荐景点{j+1}",
                    address=f"{request.city}市",
                    location=Location(
                        longitude=116.4 + i * 0.01 + j * 0.005,
                        latitude=39.9 + i * 0.01 + j * 0.005
                    ),
                    visit_duration=120,
                    description=f"这是{request.city}的著名景点，值得一游。",
                    category="景点",
                    ticket_price=60 if j == 0 else 30
                )
                for j in range(2)
            ],
            meals=[
                Meal(type="breakfast", name=f"第{i+1}天早餐", description="当地特色早餐", estimated_cost=30),
                Meal(type="lunch", name=f"第{i+1}天午餐", description="午餐推荐", estimated_cost=50),
                Meal(type="dinner", name=f"第{i+1}天晚餐", description="晚餐推荐", estimated_cost=80)
            ]
        )
        days.append(day_plan)

    return TripPlan(
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        weather_info=[],
        overall_suggestions=(
            f"这是为您规划的{request.city}{request.travel_days}日游行程(备用计划)。"
            f"建议提前查看各景点的开放时间和门票信息。"
            f"由于系统暂时无法获取实时数据，此计划为模板行程，"
            f"您可以根据实际需求进行调整。"
        ),
        budget=Budget(
            total_attractions=90 * request.travel_days,
            total_hotels=400 * max(request.travel_days - 1, 1),
            total_meals=160 * request.travel_days,
            total_transportation=50 * request.travel_days,
            total=(90 + 400 + 160 + 50) * request.travel_days - 400
        )
    )


# ============ 单例模式 ============

_multi_agent_planner: Optional[MultiAgentTripPlanner] = None


def get_trip_planner_agent() -> MultiAgentTripPlanner:
    """获取多智能体旅行规划系统实例(单例模式)"""
    global _multi_agent_planner

    if _multi_agent_planner is None:
        _multi_agent_planner = MultiAgentTripPlanner()

    return _multi_agent_planner
