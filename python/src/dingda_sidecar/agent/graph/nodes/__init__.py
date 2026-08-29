"""比价 Graph 节点包（按执行顺序）。

    web_research → article_analyze → planner → crawl
    → normalize → match → analyze → finalize

买家回复节点在 ``agent.workflows.buyer_reply``（guard / generate），不在此包。
"""

from dingda_sidecar.agent.graph.nodes.analyze import analyze_node
from dingda_sidecar.agent.graph.nodes.articles import article_analyze_node
from dingda_sidecar.agent.graph.nodes.finalize import finalize_node
from dingda_sidecar.agent.graph.nodes.match import match_node
from dingda_sidecar.agent.graph.nodes.normalize import normalize_node
from dingda_sidecar.agent.graph.nodes.planner import planner_node
from dingda_sidecar.agent.graph.nodes.search import crawl_node, web_research_node

__all__ = [
    "analyze_node",
    "article_analyze_node",
    "crawl_node",
    "finalize_node",
    "match_node",
    "normalize_node",
    "planner_node",
    "web_research_node",
]
