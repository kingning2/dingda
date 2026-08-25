"""最小 LangGraph agent：`planner → final`。

懒加载 `langgraph` / `openai`：sidecar 未安装依赖时，模块可安全导入，
仅 `run_reply` 调用时才真正实例化图与客户端。
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    query: str
    plan: str
    reply: str


def run_reply(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
    """跑一遍 `planner → final` 图，返回最终回复。"""
    from langgraph.graph import END, StateGraph

    from sidecar.agents.llm import chat, create_client

    client = create_client(base_url, api_key)

    def planner(state: AgentState) -> dict[str, str]:
        plan = chat(
            client,
            model,
            system,
            f"请先给出执行计划（1-3 步）。用户需求：{state['query']}",
        )
        return {"plan": plan}

    def final(state: AgentState) -> dict[str, str]:
        reply = chat(
            client,
            model,
            system,
            f"用户需求：{state['query']}\n计划：{state['plan']}\n请给出最终回复。",
        )
        return {"reply": reply}

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner)
    graph.add_node("final", final)
    graph.add_edge("planner", "final")
    graph.add_edge("final", END)
    graph.set_entry_point("planner")

    compiled = graph.compile()
    result = compiled.invoke({"query": user, "plan": "", "reply": ""})
    return result["reply"]
