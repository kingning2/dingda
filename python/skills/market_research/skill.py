"""market_research skill 规格 — 给 AI 的描述、入参与工具绑定。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from skills.registry import register_skill
from skills.spec import SkillSpec

SKILL_ID = "market_research"

# LangChain tool-loop（web_research 节点）使用的子集
RESEARCH_TOOL_NAMES: tuple[str, ...] = ("web_fetch", "web_scrape")

TOOL_NAMES: tuple[str, ...] = (
    "web_fetch",
    "web_scrape",
    "alibaba_search",
    "xianyu_search",
    "knowledge_retrieve",
)


class MarketResearchParams(BaseModel):
    """调用本 skill 时的入参（AI / 上游可见，Field.description 进 schema）。"""

    query: str = Field(description="用户选品、比价或找货源的需求原文")
    system: str = Field(
        default="",
        description="可选补充说明（约束、品类偏好、预算等），可为空",
    )
    account_id: str = Field(
        default="",
        description="可选；渠道核验（闲鱼/1688）时使用的已登录账号 ID",
    )


SPEC = SkillSpec(
    id=SKILL_ID,
    name="市场调研 / 比价选品",
    description=(
        "面向闲鱼与 1688 的选品调研技能。"
        "流程：先用 web_fetch/web_scrape 联网收集公开材料，再分析与规划关键词，"
        "必要时用 xianyu_search/alibaba_search 核验真实挂价与货源，最后整理成文。"
        "适用于：查行情、比价、找可卖品类、验证某款货是否好卖。"
        "不适用于：闲聊、与选品无关的通用问答。"
    ),
    parameters=MarketResearchParams,
    tools=TOOL_NAMES,
)


def register() -> None:
    register_skill(SPEC)


def research_tools():
    from skills.registry import langchain_tools_for_skill

    return langchain_tools_for_skill(SKILL_ID, only=RESEARCH_TOOL_NAMES)


register()
