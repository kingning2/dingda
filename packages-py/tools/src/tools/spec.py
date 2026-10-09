"""Tool 注册信息。

职责：
    定义 ``ToolSpec``——一个可注册 Tool 的契约快照（名称 / 描述 / 输入输出模型 /
    handler / 超时）。单独成模块，避免 registry ↔ 各工具目录互相 import 成环。

设计说明：
    - registry 用 ``pkgutil`` 自动发现 ``tools/<name>/`` 子包并读取其 ``spec`` 属性
    - 各工具目录在 ``__init__.py`` 里构造 ``spec = ToolSpec(...)``

使用示例：
    from tools.spec import ToolSpec
    spec = ToolSpec(name="search", description="...", input_model=SearchInput,
                    output_model=SearchOutput, handler=run_search, timeout_s=300.0)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolSpec:
    """单个 Tool 的注册信息。"""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[..., Awaitable[BaseModel]]
    timeout_s: float
    # 只给特定 agent 用（如修复子 agent 的校验工具）：默认面不暴露
    internal_only: bool = False
