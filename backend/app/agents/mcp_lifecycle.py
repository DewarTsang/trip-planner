"""MCP客户端生命周期管理

管理amap-mcp-server子进程的启动、工具加载和关闭。
在FastAPI lifespan中调用，确保MCP工具在整个应用生命周期中可用。
"""

from typing import List, Optional, Dict, Any
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from ..config import get_settings

_client: Optional[MultiServerMCPClient] = None
_amap_tools: List[BaseTool] = []


async def init_mcp_client():
    """初始化MCP客户端并连接高德地图MCP服务器

    使用 langchain-mcp-adapters 0.3.x 的新API:
    MultiServerMCPClient(server_configs) + await client.get_tools()

    在FastAPI startup时调用。启动amap-mcp-server子进程并加载其工具。
    如果启动失败，会打印警告但不会阻止应用启动。
    """
    global _client, _amap_tools

    settings = get_settings()

    if not settings.amap_api_key:
        print("⚠️  AMAP_API_KEY未配置，跳过MCP客户端初始化")
        return

    try:
        print("🔄 正在初始化MCP客户端...")
        print(f"   启动命令: uvx amap-mcp-server")

        # langchain-mcp-adapters 0.3.x API:
        # 传入服务器配置字典，不再使用 context manager
        # server_configs: Dict[str, Dict[str, Any]] = {
        #     "amap": {
        #         "transport": "stdio",
        #         "command": "uvx",
        #         "args": ["amap-mcp-server"],
        #         "env": {"AMAP_MAPS_API_KEY": settings.amap_api_key},
        #     }
        # }
        server_configs: Dict[str, Dict[str, Any]] = {
            "amap": {
                "transport": "http",
                "url": f"https://mcp.amap.com/mcp?key={settings.amap_api_key}",
            }
        }

        _client = MultiServerMCPClient(server_configs)
        _amap_tools = await _client.get_tools()

        print(f"✅ MCP客户端初始化成功")
        print(f"   已加载 {len(_amap_tools)} 个工具:")
        for tool in _amap_tools[:8]:
            desc = tool.description[:60] if tool.description else "(no description)"
            print(f"     - {tool.name}: {desc}...")
        if len(_amap_tools) > 8:
            print(f"     ... 还有 {len(_amap_tools) - 8} 个工具")

    except Exception as e:
        print(f"⚠️  MCP客户端初始化失败: {e}")
        print(f"   地图服务将不可用，但应用仍可启动")
        import traceback
        traceback.print_exc()
        _client = None
        _amap_tools = []


async def shutdown_mcp_client():
    """关闭MCP客户端，停止amap-mcp-server子进程

    在FastAPI shutdown时调用。
    langchain-mcp-adapters 0.3.x 的 MultiServerMCPClient
    不需要显式关闭（工具连接在垃圾回收时自动清理）。
    """
    global _client, _amap_tools

    if _client:
        try:
            print("🔄 正在关闭MCP客户端...")
            # MultiServerMCPClient 0.3.x 没有显式的 close/__aexit__
            # 子进程会在垃圾回收时自动清理
            print("✅ MCP客户端已关闭")
        except Exception as e:
            print(f"⚠️  MCP客户端关闭时出错: {e}")
        finally:
            _client = None
            _amap_tools = []


def get_amap_tools() -> List[BaseTool]:
    """获取高德地图MCP工具列表(单例)

    Returns:
        LangChain BaseTool列表

    Raises:
        RuntimeError: MCP客户端未初始化时抛出
    """
    if not _amap_tools:
        raise RuntimeError(
            "MCP客户端未初始化。请确保应用已通过lifespan启动，"
            "且AMAP_API_KEY已正确配置。"
        )
    return _amap_tools


def _find_tool_by_name(tools: List[BaseTool], name: str) -> BaseTool:
    """按名称查找工具

    Args:
        tools: 工具列表
        name: 工具名称（支持部分匹配）

    Returns:
        匹配的BaseTool

    Raises:
        ValueError: 未找到匹配工具时抛出
    """
    # 精确匹配
    for tool in tools:
        if tool.name == name:
            return tool

    # 部分匹配
    for tool in tools:
        if name in tool.name:
            return tool

    available = [t.name for t in tools]
    raise ValueError(f"未找到工具 '{name}'。可用工具: {available}")
