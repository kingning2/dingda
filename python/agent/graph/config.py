"""Graph 运行时配置。

从 AiSettings 派生 GraphConfig（模型、温度、知识开关等），注入 GraphContext。"""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import AiSettings


@dataclass(frozen=True)
class GraphConfig:
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    system: str = ""
    max_search_results: int = 5
    ai_settings: AiSettings | None = None

    @classmethod
    def from_ai_settings(cls, settings: AiSettings, *, system: str = "") -> GraphConfig:
        return cls(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model_name,
            system=system,
            ai_settings=settings,
        )
