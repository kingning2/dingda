"""模型配置 HTTP 路由。

职责：
    供应商目录、可用模型列表、模型凭据的增删改查、设为使用中、连通性检测、从环境变量导入。

设计说明：
    - **供应商目录在这一层转换并注入**：目录的真相在 ``agent.llm.providers``，而
      ``domains`` 不许 import ``agent``。``api`` 是唯一同时认识两边的地方，
      所以由这里把目录转成 ``contracts.llm`` 的形状喂给领域服务
    - **组装 ``LlmClient`` 需要 key 原文，而 key 不进任何契约** —— 所以检测端点与模型列表
      端点都直接读 ``infrastructure.db.llm_credentials``，不经领域服务。领域服务管的是
      凭据生命周期，不是客户端构造
    - **模型列表与检测共用一套口径**：都回 200 + ``ok=false``，都带 ``llm.*`` 精确错误码。
      「这把 key 拉不到列表」是业务结果 —— 回 4xx 会让前端既弹错误框、又收一份结果，
      两条路径说同一件事。用户在表单里填错 key 时该看到「API key 无效或已过期」
    - **检测是只读探活**：不写 ``updated_at``，不改变使用中的那条
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter

from agent.llm.client import LlmClient
from agent.llm.models import LlmSettings
from agent.llm.providers import list_providers, resolve_settings
from contracts.llm import (
    LlmCheckResponse,
    LlmCheckView,
    LlmCredentialCreateRequest,
    LlmCredentialDeleteResponse,
    LlmCredentialListResponse,
    LlmCredentialResponse,
    LlmCredentialUpdateRequest,
    LlmImportEnvResponse,
    LlmModelListRequest,
    LlmModelListResponse,
    LlmProviderListResponse,
    LlmProviderView,
)
from core.errors import AppError
from domains.llm.service import LlmCredentialService
from infrastructure.db import llm_credentials as credential_repo

logger = logging.getLogger("dingda.api.llm")

router = APIRouter(prefix="/v1/llm", tags=["llm"])

PROBE_TIMEOUT_S = 20.0
"""探活与拉模型列表的超时都比正式调用短：用户盯着按钮等，60 秒的默认值体验太差。"""

PROBE_MAX_TOKENS = 16
"""探活只要「模型回话了」这个信号，不要长回答。"""

PROBE_MESSAGE = "ping"
"""探活内容。刻意与业务无关 —— 这一句的成败只说明连通性。"""

MODELS_PLACEHOLDER = "(models)"
"""拉模型列表时占位的 ``model``：``models.list()`` 不看它，``LlmSettings`` 又要求非空。

填占位符比把 ``LlmSettings.model`` 改成可选更省事 —— 后者会给所有调用点加一层
「可能为空」的判断，而真正需要 model 的地方只有 ``chat`` / ``stream``。
"""

EMPTY_MODELS_HINT = "上游没有返回任何模型，可以手动填写模型名"
"""上游 ``data`` 为空时的提示。这不是错误 —— 有的网关就是不给列表（如方舟的接入点）。"""


def _catalog() -> dict[str, LlmProviderView]:
    """``agent`` 的供应商目录 → 契约形状，按 id 建索引。

    ``requires_model`` 由「有没有默认模型」推出：豆包只认 ``ep-`` 接入点 ID，
    没有默认值，前端必须把模型字段标成必填。
    """
    return {
        item.id: LlmProviderView(
            id=item.id,
            name=item.name,
            base_url=item.base_url,
            default_model=item.default_model,
            api_key_envs=list(item.api_key_envs),
            requires_model=item.default_model is None,
        )
        for item in list_providers()
    }


def _service() -> LlmCredentialService:
    """按请求建服务：目录是进程内常量，服务本身无状态，不值得缓存。"""
    return LlmCredentialService(catalog=_catalog())


def _require_row(credential_id: str) -> credential_repo.LlmCredentialRow:
    """取凭据行；不存在报 404。"""
    row = credential_repo.get_credential(credential_id.strip())
    if row is None:
        raise AppError("llm.credential_not_found", "模型凭据不存在", status_code=404)
    return row


def _require_provider(provider: str) -> LlmProviderView:
    """取目录里的一行；不在目录里报 400。

    目录是**唯一**的供应商事实来源：默认地址、默认模型、有没有默认模型都从这里取，
    别在别处再写一份 ``if provider == "doubao"``。
    """
    entry = _catalog().get((provider or "").strip().lower())
    if entry is None:
        known = " / ".join(sorted(_catalog()))
        raise AppError(
            "llm.provider_unsupported",
            f"不认识的 LLM 供应商 {provider or '(空)'}，只支持 {known}",
            status_code=400,
        )
    return entry


def _probe_client(row: credential_repo.LlmCredentialRow) -> LlmClient:
    """按一条凭据建探活客户端。

    ``base_url`` 为空时回落到供应商默认地址 —— 与领域服务补 ``effective_base_url``
    同一个口径，两处必须一致，否则页面显示一个地址、实际请求另一个。
    """
    entry = _require_provider(row.provider)
    return LlmClient(
        LlmSettings(
            provider_id=row.provider,
            base_url=row.base_url or entry.base_url,
            model=row.model,
            api_key=row.api_key,
            timeout_s=PROBE_TIMEOUT_S,
            max_retries=0,
        )
    )


async def _fetch_models(*, provider: str, base_url: str, api_key: str) -> list[str]:
    """按一组连接参数拉可用模型；失败抛 ``AppError``，由调用方转成 200 + ``ok=false``。

    只建一次客户端就关掉：这一步不写库、不改状态，纯粹是「拿这把 key 问一句上游」。
    """
    client = LlmClient(
        LlmSettings(
            provider_id=provider,
            base_url=base_url,
            model=MODELS_PLACEHOLDER,
            api_key=api_key,
            timeout_s=PROBE_TIMEOUT_S,
            max_retries=0,
        )
    )
    try:
        return await client.list_models()
    finally:
        await client.aclose()


@router.get("/providers", response_model=LlmProviderListResponse)
def list_llm_providers() -> LlmProviderListResponse:
    """可选供应商目录（前端下拉的数据源）。"""
    return _service().list_providers()


@router.post("/models", response_model=LlmModelListResponse)
async def list_llm_models(request: LlmModelListRequest) -> LlmModelListResponse:
    """按一组连接参数拉可用模型（凭据**还没保存**时用）。

    表单里刚粘上 key 就能拉，不必先存一条废凭据再删。
    """
    entry = _require_provider(request.provider)
    base_url = (request.base_url or "").strip() or entry.base_url
    try:
        models = await _fetch_models(
            provider=entry.id,
            base_url=base_url,
            api_key=request.api_key.strip(),
        )
    except AppError as exc:
        logger.warning("拉模型列表失败 provider=%s code=%s", entry.id, exc.code)
        # 失败也带上 default_model：前端这时要退回手填输入框，用默认模型预填比留空好；
        # 而且「provider=deepseek 却 default_model=null」与 /providers 的说法自相矛盾
        return LlmModelListResponse(
            ok=False,
            provider=entry.id,
            default_model=entry.default_model,
            message=exc.message,
        )
    logger.info("拉模型列表完成 provider=%s count=%s", entry.id, len(models))
    return LlmModelListResponse(
        provider=entry.id,
        models=models,
        default_model=entry.default_model,
        message=None if models else EMPTY_MODELS_HINT,
    )


@router.get("/credentials/{credential_id}/models", response_model=LlmModelListResponse)
async def list_credential_models(credential_id: str) -> LlmModelListResponse:
    """用已保存凭据的 key 拉可用模型。

    编辑态**必须**走这条：key 只回掩码，浏览器里根本没有原文。
    """
    row = _require_row(credential_id)
    entry = _require_provider(row.provider)
    try:
        models = await _fetch_models(
            provider=row.provider,
            base_url=row.base_url or entry.base_url,
            api_key=row.api_key,
        )
    except AppError as exc:
        logger.warning("拉模型列表失败 id=%s code=%s", row.credential_id, exc.code)
        return LlmModelListResponse(
            ok=False,
            provider=row.provider,
            default_model=entry.default_model,
            current_model=row.model,
            message=exc.message,
        )
    logger.info("拉模型列表完成 id=%s count=%s", row.credential_id, len(models))
    return LlmModelListResponse(
        provider=row.provider,
        models=models,
        default_model=entry.default_model,
        current_model=row.model,
        message=None if models else EMPTY_MODELS_HINT,
    )


@router.get("/credentials", response_model=LlmCredentialListResponse)
def list_llm_credentials() -> LlmCredentialListResponse:
    """全部模型凭据 + 当前使用中的 id。"""
    return _service().list()


@router.post("/credentials", response_model=LlmCredentialResponse)
def create_llm_credential(request: LlmCredentialCreateRequest) -> LlmCredentialResponse:
    """新建一条凭据。"""
    return _service().create(request)


@router.post("/credentials/import-env", response_model=LlmImportEnvResponse)
def import_llm_credential_from_env() -> LlmImportEnvResponse:
    """把 ``.env`` / 真实环境里的那份配置收编成一条凭据。

    环境里没配或配不全时**不报错**：这是一次「探测有没有可导入的东西」，
    空手而归是正常结果，不是失败。
    """
    try:
        settings = resolve_settings()
    except AppError as exc:
        logger.info("环境变量里没有可导入的模型配置 code=%s", exc.code)
        return LlmImportEnvResponse(imported=False, message=f"环境变量里没有可导入的配置：{exc.message}")
    return _service().import_from_env(
        provider=settings.provider_id,
        model=settings.model,
        base_url=settings.base_url,
        api_key=settings.api_key,
    )


@router.put("/credentials/{credential_id}", response_model=LlmCredentialResponse)
def update_llm_credential(
    credential_id: str,
    request: LlmCredentialUpdateRequest,
) -> LlmCredentialResponse:
    """改一条凭据；请求里没出现的字段就是不改。"""
    return _service().update(credential_id.strip(), request)


@router.delete("/credentials/{credential_id}", response_model=LlmCredentialDeleteResponse)
def delete_llm_credential(credential_id: str) -> LlmCredentialDeleteResponse:
    """删一条凭据。"""
    return _service().delete(credential_id.strip())


@router.post("/credentials/{credential_id}/activate", response_model=LlmCredentialResponse)
def activate_llm_credential(credential_id: str) -> LlmCredentialResponse:
    """把某条设为唯一使用中。"""
    return _service().activate(credential_id.strip())


@router.post("/credentials/{credential_id}/test", response_model=LlmCheckResponse)
async def test_llm_credential(credential_id: str) -> LlmCheckResponse:
    """发一次最小请求验连通性，并把结果记到该条凭据上。

    **永远回 200**：探活失败是「这条凭据不好使」这个业务结果，不是 HTTP 层错误。
    回 4xx/5xx 会让前端既收到错误弹窗、又收到一份检测结果，两条路径说同一件事。
    """
    row = _require_row(credential_id)
    service = _service()
    client = _probe_client(row)
    messages: list[dict[str, Any]] = [{"role": "user", "content": PROBE_MESSAGE}]

    try:
        started = time.perf_counter()
        # compress=False：探活要的是「这条线路通不通」，压缩层出问题不该算到凭据头上
        result = await client.chat(messages, max_tokens=PROBE_MAX_TOKENS, compress=False)
    except AppError as exc:
        service.record_check(row.credential_id, ok=False, message=exc.message)
        logger.warning(
            "模型凭据检测失败 id=%s provider=%s code=%s",
            row.credential_id,
            row.provider,
            exc.code,
        )
        return LlmCheckResponse(
            check=LlmCheckView(
                ok=False,
                code=exc.code,
                message=exc.message,
                provider=row.provider,
                model=row.model,
            )
        )
    finally:
        await client.aclose()

    latency_ms = int((time.perf_counter() - started) * 1000)
    reply = result.text.strip()[:60] or None
    service.record_check(row.credential_id, ok=True, message=f"连通，耗时 {latency_ms} ms")
    logger.info(
        "模型凭据检测通过 id=%s provider=%s model=%s latency_ms=%s",
        row.credential_id,
        row.provider,
        result.model or row.model,
        latency_ms,
    )
    return LlmCheckResponse(
        check=LlmCheckView(
            ok=True,
            message=f"连通，耗时 {latency_ms} ms",
            latency_ms=latency_ms,
            reply=reply,
            provider=row.provider,
            model=result.model or row.model,
        )
    )
