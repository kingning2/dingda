"""AI 回复设置 — 对齐 Rust ``AiSettings`` / 业务 ``ai-config.json``。

解析营业时段、议价上限、自动回复开关等，并派生可用的 Provider 配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from config.models import ProviderSettings
from llm.factory import normalize_provider_type


@dataclass
class AiSettings:
    ai_enabled: bool = False
    provider_type: str = "openai_compatible"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model_name: str = "qwen-plus"
    max_bargain_rounds: int = 3
    max_discount_percent: int = 10
    max_discount_amount: int = 100
    custom_prompts: dict[str, str] = field(default_factory=dict)
    time_range_start: str = ""
    time_range_end: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AiSettings:
        """从 IPC / agent reply payload 解析。"""
        custom = payload.get("custom_prompts")
        prompts: dict[str, str] = {}
        if isinstance(custom, dict):
            prompts = {str(k): str(v) for k, v in custom.items() if v}

        return cls(
            ai_enabled=bool(payload.get("ai_enabled", True)),
            provider_type=str(
                payload.get("provider_type") or payload.get("kind") or "openai_compatible"
            ),
            api_key=str(payload.get("api_key", "")).strip(),
            base_url=str(payload.get("base_url", "")).strip()
            or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_name=str(
                payload.get("model_name") or payload.get("model") or "qwen-plus"
            ).strip(),
            max_bargain_rounds=int(payload.get("max_bargain_rounds") or 3),
            max_discount_percent=int(payload.get("max_discount_percent") or 10),
            max_discount_amount=int(payload.get("max_discount_amount") or 100),
            custom_prompts=prompts,
            time_range_start=str(payload.get("time_range_start") or "").strip(),
            time_range_end=str(payload.get("time_range_end") or "").strip(),
        )

    def normalized_provider_type(self) -> str:
        return normalize_provider_type(self.provider_type, self.base_url, self.model_name)

    def to_provider_settings(self) -> ProviderSettings:
        return ProviderSettings(
            provider_type=self.normalized_provider_type(),
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model_name,
        )

    def in_time_range(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        now_min = now.hour * 60 + now.minute
        start, end = self.time_range_start.strip(), self.time_range_end.strip()
        if not start or not end:
            return True
        start_min = _parse_hhmm(start)
        end_min = _parse_hhmm(end)
        if start_min is None or end_min is None:
            return True
        if start_min <= end_min:
            return start_min <= now_min <= end_min
        return now_min >= start_min or now_min <= end_min


def _parse_hhmm(value: str) -> int | None:
    parts = value.split(":")
    if not parts:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return None
    return hour * 60 + minute
