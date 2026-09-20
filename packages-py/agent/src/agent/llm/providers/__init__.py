"""LLM 供应商注册表与配置解析。

职责：
    按 id 取出厂家目录行；把「显式入参 → 环境变量 → 供应商默认」压成 ``LlmSettings``。
    厂家事实各自放在 ``providers/<id>.py``，这里只登记、不写厂家特例。

设计说明：
    - **环境变量在调用时读，不在 import 时读**（``agent.core.compress`` 的默认模型也是）。
    - 日志**绝不带 key 原文**；base_url 与供应商默认不一致时打 warning。
"""

from __future__ import annotations

import logging
import os

from core.errors import AppError

from agent.llm.models import LlmSettings
from agent.llm.providers.base import CatalogProvider
from agent.llm.providers.deepseek import PROVIDER as DEEPSEEK
from agent.llm.providers.doubao import PROVIDER as DOUBAO
from agent.llm.providers.doubao_coding import PROVIDER as DOUBAO_CODING

logger = logging.getLogger("dingda.agent.llm.providers")

_DEFAULT_PROVIDER = "deepseek"
_DEFAULT_TIMEOUT_S = 60.0
_DEFAULT_MAX_RETRIES = 2

# 唯一登记处：新增厂家 = 加文件 + 这里加一行。
_CATALOG: tuple[CatalogProvider, ...] = (DEEPSEEK, DOUBAO, DOUBAO_CODING)


def list_providers() -> list[CatalogProvider]:
    """全部供应商，按 id 排序（顺序稳定才好比对）。"""
    return sorted(_CATALOG, key=lambda item: item.id)


def get_provider(provider_id: str) -> CatalogProvider:
    """按 id 取供应商；未知的抛 ``llm.provider_unsupported``。"""
    key = (provider_id or "").strip().lower()
    for item in _CATALOG:
        if item.id == key:
            return item
    known = " / ".join(item.id for item in list_providers())
    raise AppError(
        "llm.provider_unsupported",
        f"不认识的 LLM 供应商 {provider_id or '(空)'}，只支持 {known}",
        status_code=400,
    )


def _pick(*candidates: str | None) -> str:
    """取第一个非空字符串；全空归空串。**空串要落到下一级，不当成覆盖值**。"""
    for item in candidates:
        text = (item or "").strip()
        if text:
            return text
    return ""


def _env(*names: str) -> str:
    """按顺序读环境变量，取第一个非空值（不缓存，每次调用都重读）。"""
    return _pick(*(os.getenv(name) for name in names))


def resolve_settings(
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> LlmSettings:
    """把三级优先级压成一个 ``LlmSettings``：显式入参 → 环境变量 → 供应商默认。

    ``api_key`` 的兜底链：``DINGDA_LLM_API_KEY`` → ``OPENAI_API_KEY`` → 供应商专属变量。
    key 全空抛 ``llm.api_key_missing``，model 仍为空抛 ``llm.model_required``。
    """
    selected = get_provider(_pick(provider, _env("DINGDA_LLM_PROVIDER")) or _DEFAULT_PROVIDER)

    resolved_base_url = _pick(base_url, _env("DINGDA_LLM_BASE_URL")) or selected.base_url
    if resolved_base_url != selected.base_url:
        logger.warning(
            "LLM base_url 被覆盖 provider=%s default=%s effective=%s",
            selected.id,
            selected.base_url,
            resolved_base_url,
        )

    resolved_model = _pick(model, _env("DINGDA_LLM_MODEL")) or (selected.default_model or "")
    if not resolved_model:
        raise AppError(
            "llm.model_required",
            f"{selected.name} 没法定默认模型，请显式指定（豆包要填推理接入点 ID，形如 ep-xxxx）",
            status_code=400,
        )

    resolved_key = _pick(
        api_key,
        _env("DINGDA_LLM_API_KEY"),
        _env("OPENAI_API_KEY"),
        _env(*selected.api_key_envs),
    )
    if not resolved_key:
        expected = " / ".join(("DINGDA_LLM_API_KEY", "OPENAI_API_KEY", *selected.api_key_envs))
        raise AppError(
            "llm.api_key_missing",
            f"没找到 {selected.name} 的 API key，请设置 {expected} 之一",
            status_code=401,
        )

    settings = LlmSettings(
        provider_id=selected.id,
        base_url=resolved_base_url,
        model=resolved_model,
        api_key=resolved_key,
        timeout_s=_env_float("DINGDA_LLM_TIMEOUT", _DEFAULT_TIMEOUT_S),
        max_retries=_env_int("DINGDA_LLM_MAX_RETRIES", _DEFAULT_MAX_RETRIES),
    )
    logger.info(
        "LLM 配置就绪 provider=%s model=%s base_url=%s timeout=%ss",
        settings.provider_id,
        settings.model,
        settings.base_url,
        settings.timeout_s,
    )
    return settings


def _env_float(name: str, default: float) -> float:
    """读一个正的浮点环境变量；没填或读不动就用默认值。"""
    raw = _env(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("环境变量不是数字，用默认值 name=%s value=%s", name, raw)
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    """读一个非负的整数环境变量；没填或读不动就用默认值。"""
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("环境变量不是整数，用默认值 name=%s value=%s", name, raw)
        return default
    return value if value >= 0 else default


__all__ = [
    "CatalogProvider",
    "get_provider",
    "list_providers",
    "resolve_settings",
]
