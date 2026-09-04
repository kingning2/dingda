"""Knowledge 领域服务。

职责：
    知识库相关能力：
    - 文档/网页内容索引与分块
    - 向量嵌入与相似度检索（RAG）
    - 为 Agent 提供 ``retrieve`` 工具的数据源

迁移来源：
    旧版 ``dingda_sidecar.agent.knowledge`` 与 ``runtime/knowledge``

设计约定：
    - 向量库实现（如 Qdrant）放在 ``infrastructure`` 或本子域 ``stores/``
    - 检索接口对 Agent 层暴露稳定 API，隐藏存储细节
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dingda.knowledge")


class KnowledgeService:
    """知识库应用服务：索引、检索、删除知识条目。"""

    # 从 dingda_sidecar.agent.knowledge + runtime/knowledge 迁移实现
