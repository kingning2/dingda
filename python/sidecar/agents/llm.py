"""OpenAI 兼容 LLM 客户端（LangGraph agent 用）。

懒加载 `openai`，sidecar 未安装该依赖时其余路由仍可正常工作。
"""

from __future__ import annotations

from typing import Any


def create_client(base_url: str, api_key: str) -> Any:
    """构造 OpenAI 兼容客户端（base_url 指向任意 OpenAI 兼容端点）。"""
    from openai import OpenAI

    return OpenAI(base_url=base_url, api_key=api_key)


def chat(client: Any, model: str, system: str, user: str) -> str:
    """单轮 chat completion，返回文本。"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content
    return content if content is not None else ""
