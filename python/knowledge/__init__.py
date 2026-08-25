"""知识库能力包。

再导出 ``knowledge.service`` 中的商品知识与检索服务入口。"""

from knowledge.service import ItemKnowledge, KnowledgeService, build_item_context

__all__ = ["ItemKnowledge", "KnowledgeService", "build_item_context"]
