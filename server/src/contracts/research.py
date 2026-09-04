"""Research API 契约模型。

定义市场调研/机会分析相关 HTTP 接口的数据结构。
与 ``contracts/schema/v1/research`` 对齐。

当前模型：
    ResearchRunRequest  启动一次调研运行

后续扩展：
    机会条目、评分维度、报告摘要、分页列表等响应模型。
"""

from __future__ import annotations

from pydantic import BaseModel


class ResearchRunRequest(BaseModel):
    """启动调研任务的请求体。"""

    task_id: str
    query: str
