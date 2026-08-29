"""Knowledge 子 runtime 包。"""

from dingda_sidecar.runtime.knowledge.runtime import (
    KnowledgeRuntime,
    get_knowledge_runtime,
    get_knowledge_service,
)

__all__ = ["KnowledgeRuntime", "get_knowledge_runtime", "get_knowledge_service"]
