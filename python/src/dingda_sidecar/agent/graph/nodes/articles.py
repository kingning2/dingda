"""② article_analyze — 多篇网页材料 → 高利润品类结论（业务写在本节点）。

读：``query``、``web_context``、``knowledge_context``
写：``analysis``
"""

from __future__ import annotations

from dingda_sidecar.agent.graph.context import GraphContext
from dingda_sidecar.agent.graph.state import GraphState


def article_analyze_node(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    """综合多篇材料，归纳哪些商品/品类声称利润较高。"""
    query = state.get("query", "")
    web = state.get("web_context", "")
    knowledge = state.get("knowledge_context", "")
    prompt = (
        f"用户关注品类：{query}\n"
        f"网上多篇材料：\n{web or '（无）'}\n"
        f"知识库补充：{knowledge or '（无）'}\n"
        "请综合多篇材料，分析当前哪些商品/细分品类利润相对较高：\n"
        "- 列出 3-5 个候选（越具体越好）\n"
        "- 每条写清依据（哪类材料提到、是否交叉验证）\n"
        "- 标注不确定之处（广告软文、过时信息等）\n"
        "不要给出最终购买建议；后续还要用爬虫核验。"
    )
    return {"analysis": ctx.llm(prompt)}
