"""高德地图MCP服务封装 — 基于LangChain MCP Adapters"""

import json
import re
from typing import List, Dict, Any, Optional
from ..agents.mcp_lifecycle import get_amap_tools, _find_tool_by_name
from ..models.schemas import Location, POIInfo, WeatherInfo


class AmapService:
    """高德地图服务封装类

    使用 LangChain MCP Adapters 加载的工具列表。工具在应用启动时预加载，
    通过 get_amap_tools() 获取。
    """

    def __init__(self):
        """初始化服务 — 工具已在应用启动时通过mcp_lifecycle加载"""
        pass

    async def search_poi(
        self, keywords: str, city: str, citylimit: bool = True
    ) -> List[POIInfo]:
        """搜索POI"""
        try:
            tools = get_amap_tools()
            tool = _find_tool_by_name(tools, "maps_text_search")

            result = await tool.ainvoke({
                "keywords": keywords,
                "city": city,
                "citylimit": str(citylimit).lower()
            })

            print(f"POI搜索结果: {str(result)[:200]}...")
            return []  # TODO: 解析MCP工具返回的POI数据

        except Exception as e:
            print(f"❌ POI搜索失败: {str(e)}")
            return []

    async def get_weather(self, city: str) -> List[WeatherInfo]:
        """查询天气"""
        try:
            tools = get_amap_tools()
            tool = _find_tool_by_name(tools, "maps_weather")

            result = await tool.ainvoke({"city": city})

            print(f"天气查询结果: {str(result)[:200]}...")
            return []  # TODO: 解析天气数据

        except Exception as e:
            print(f"❌ 天气查询失败: {str(e)}")
            return []

    async def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking"
    ) -> Dict[str, Any]:
        """规划路线"""
        try:
            # 根据路线类型选择工具
            tool_map = {
                "walking": "maps_direction_walking_by_address",
                "driving": "maps_direction_driving_by_address",
                "transit": "maps_direction_transit_integrated_by_address"
            }

            tool_name = tool_map.get(route_type, "maps_direction_walking_by_address")
            tools = get_amap_tools()
            tool = _find_tool_by_name(tools, tool_name)

            # 构建参数
            arguments = {
                "origin_address": origin_address,
                "destination_address": destination_address,
            }

            if origin_city:
                arguments["origin_city"] = origin_city
            if destination_city:
                arguments["destination_city"] = destination_city

            if route_type == "transit":
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city

            result = await tool.ainvoke(arguments)

            print(f"路线规划结果: {str(result)[:200]}...")
            return {}  # TODO: 解析路线数据

        except Exception as e:
            print(f"❌ 路线规划失败: {str(e)}")
            return {}

    async def geocode(
        self, address: str, city: Optional[str] = None
    ) -> Optional[Location]:
        """地理编码(地址转坐标)"""
        try:
            tools = get_amap_tools()
            tool = _find_tool_by_name(tools, "maps_geo")

            arguments = {"address": address}
            if city:
                arguments["city"] = city

            result = await tool.ainvoke(arguments)

            print(f"地理编码结果: {str(result)[:200]}...")
            return None  # TODO: 解析坐标数据

        except Exception as e:
            print(f"❌ 地理编码失败: {str(e)}")
            return None

    async def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """获取POI详情"""
        try:
            tools = get_amap_tools()
            tool = _find_tool_by_name(tools, "maps_search_detail")

            result = await tool.ainvoke({"id": poi_id})

            print(f"POI详情结果: {str(result)[:200]}...")

            # 尝试从结果中提取JSON
            result_str = str(result)
            json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data

            return {"raw": result_str}

        except Exception as e:
            print(f"❌ 获取POI详情失败: {str(e)}")
            return {}


# 全局服务实例
_amap_service = None


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service

    if _amap_service is None:
        _amap_service = AmapService()

    return _amap_service
