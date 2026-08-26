"""知识库能力包（位于 graph）。

再导出商品知识与检索服务入口。"""

from agent.knowledge.service import ItemKnowledge, KnowledgeService, build_item_context

__all__ = ["ItemKnowledge", "KnowledgeService", "build_item_context"]
