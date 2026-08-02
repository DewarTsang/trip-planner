"""LLM服务模块 — 基于LangChain ChatOpenAI"""

import os
from langchain_openai import ChatOpenAI

# 全局LLM实例
_chat_model_instance = None


def get_chat_model() -> ChatOpenAI:
    """
    获取ChatOpenAI实例(单例模式)

    从环境变量读取LLM配置:
    - LLM_API_KEY: API密钥
    - LLM_BASE_URL: API地址
    - LLM_MODEL_ID: 模型名称
    回退支持 OPENAI_API_KEY

    Returns:
        ChatOpenAI实例
    """
    global _chat_model_instance

    if _chat_model_instance is None:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        base_url = os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"
        model = os.getenv("LLM_MODEL_ID") or "gpt-3.5-turbo"

        _chat_model_instance = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
        )

        print(f"✅ LangChain LLM服务初始化成功")
        print(f"   模型: {model}")
        print(f"   地址: {base_url}")

    return _chat_model_instance


def get_planner_llm():
    """
    获取配置了结构化输出的LLM实例(用于行程规划)

    使用 with_structured_output(method="function_calling") 直接将LLM输出
    解析为TripPlan对象。DeepSeek需要禁用thinking模式以支持function calling。

    Returns:
        配置了structured_output的Runnable
    """
    from ..models.schemas import TripPlan

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    base_url = os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"
    model = os.getenv("LLM_MODEL_ID") or "gpt-3.5-turbo"

    chat = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
        model_kwargs={
            # DeepSeek: 禁用thinking模式以启用function calling
            # OpenAI: 忽略此参数
            "extra_body": {"thinking": {"type": "disabled"}}
        },
    )

    return chat.with_structured_output(TripPlan, method="function_calling")


def reset_llm():
    """重置LLM实例(用于测试或重新配置)"""
    global _chat_model_instance
    _chat_model_instance = None
    print("🔄 LLM实例已重置")
