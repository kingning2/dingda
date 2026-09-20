"""LLM 供应商插座：目录行形状。

职责：
    定义每个厂家文件要交出的静态事实（id / base_url / 默认模型 / 能否列模型 / key 环境变量）。

设计说明：
    - 厂家之间协议同构时只差这几个**值**，不在这里写 HTTP；调用走 ``llm/client.py``。
    - 新增厂家：加一个 ``providers/<id>.py``，在 ``providers/__init__.py`` 的目录里登记一行。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogProvider:
    """目录里的一行：某个 OpenAI 兼容供应商的静态事实。"""

    id: str
    """供应商标识，也是 ``DINGDA_LLM_PROVIDER`` 认的值。"""

    name: str
    """给用户 / 日志看的中文名。"""

    base_url: str
    """OpenAI 兼容口地址。"""

    default_model: str | None
    """不填 ``DINGDA_LLM_MODEL`` 时用的模型；``None`` 表示没法定默认。"""

    supports_models: bool
    """这家是否提供 ``GET /models``。"""

    api_key_envs: tuple[str, ...]
    """本供应商专属的 key 环境变量名，按顺序逐个试。"""
