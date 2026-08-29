"""tools.knowledge — 知识检索工具。"""

from dingda_sidecar.tools.knowledge.bindings import make_knowledge_retrieve_tool
from dingda_sidecar.tools.knowledge.retrieve import retrieve_knowledge

__all__ = ["make_knowledge_retrieve_tool", "retrieve_knowledge"]
