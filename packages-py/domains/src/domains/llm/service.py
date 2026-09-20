"""模型凭据领域服务（SQLite 编排 + 展示口径）。

职责：
    模型凭据的增删改查、设为使用中、最近检测结果记录，以及「从环境变量导入」。
    对外只给 ``contracts.llm`` 的形状，**key 原文永不出这一层**（出参一律掩码）。

设计说明：
    - **供应商目录由构造方注入**（``catalog``）：目录的真相在 ``agent.llm.providers``，
      而 ``domains`` 不许 import ``agent``（依赖方向：agent → domains 是反的）。
      抄一份目录进来会立刻分叉，所以走注入口，与 ``NodeContext.cookie_resolver``
      同一个判断标准。有了它，供应商合法性校验才能留在本层而不是漏到路由里
    - **``effective_base_url`` 在这里补默认值**：库里 ``base_url`` 存 ``NULL`` 表示
      跟随供应商默认（理由见 ``infrastructure.db.llm_credentials``），补值属于展示口径
    - 掩码函数导出：测试要直接测它，别的展示点也不该各写一套
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping

from contracts.llm import (
    LlmCredentialCreateRequest,
    LlmCredentialDeleteResponse,
    LlmCredentialListResponse,
    LlmCredentialRecord,
    LlmCredentialResponse,
    LlmCredentialUpdateRequest,
    LlmImportEnvResponse,
    LlmProviderListResponse,
    LlmProviderView,
)
from core.errors import AppError
from infrastructure.db import llm_credentials as credential_repo

logger = logging.getLogger("dingda.llm.service")

MASK_HEAD = 6
"""掩码保留的前缀长度：够认出「这是哪一把」，不够被拿去用。"""

MASK_TAIL = 4
"""掩码保留的后缀长度：用户靠它比对自己在别处存的那把 key。"""


def mask_api_key(api_key: str) -> str:
    """key 原文 → 展示用掩码。

    短于「前 6 + 后 4」的 key 全星号 —— 否则掩码本身就把 key 泄完了。
    """
    text = (api_key or "").strip()
    if not text:
        return ""
    if len(text) <= MASK_HEAD + MASK_TAIL:
        return "*" * len(text)
    return f"{text[:MASK_HEAD]}****{text[-MASK_TAIL:]}"


class LlmCredentialService:
    """凭据领域服务。``catalog`` 是「供应商 id → 供应商事实」的映射。"""

    def __init__(self, *, catalog: Mapping[str, LlmProviderView]) -> None:
        self._catalog = dict(catalog)

    def list_providers(self) -> LlmProviderListResponse:
        """供应商目录，按 id 排序（顺序稳定，前端下拉才不跳）。"""
        return LlmProviderListResponse(items=[self._catalog[key] for key in sorted(self._catalog)])

    def list(self) -> LlmCredentialListResponse:
        """全部凭据 + 当前使用中的 id。"""
        rows = credential_repo.list_credentials()
        items = [self._to_record(row) for row in rows]
        active = next((item.credential_id for item in items if item.is_active), None)
        return LlmCredentialListResponse(items=items, active_id=active)

    def create(self, request: LlmCredentialCreateRequest) -> LlmCredentialResponse:
        """新建一条凭据；``activate=True`` 时顺手设为使用中。"""
        provider = self._require_provider(request.provider)
        api_key = (request.api_key or "").strip()
        if not api_key:
            raise AppError("llm.api_key_missing", "API key 不能为空", status_code=400)

        model = (request.model or "").strip() or (provider.default_model or "")
        if not model:
            raise AppError(
                "llm.model_required",
                f"{provider.name} 没有默认模型，必须手填（豆包要填推理接入点 ID，形如 ep-xxxx）",
                status_code=400,
            )

        credential_id = f"cred-{uuid.uuid4().hex[:12]}"
        row = credential_repo.upsert_credential(
            credential_id=credential_id,
            provider=provider.id,
            model=model,
            api_key=api_key,
            label=(request.label or "").strip(),
            base_url=request.base_url,
        )
        if request.activate:
            row = credential_repo.set_active(credential_id) or row
        logger.info(
            "模型凭据已新建 id=%s provider=%s model=%s active=%s",
            credential_id,
            provider.id,
            model,
            row.is_active,
        )
        return LlmCredentialResponse(item=self._to_record(row))

    def update(
        self,
        credential_id: str,
        request: LlmCredentialUpdateRequest,
    ) -> LlmCredentialResponse:
        """改一条凭据：**字段没出现在请求里就是不改**。

        ``base_url`` 是唯一需要区分「不改」与「清空」的字段：请求里出现且为 ``None``
        表示恢复供应商默认地址。判据是 ``model_fields_set`` —— 靠 ``None`` 本身分不开
        「没传」和「传了 null」。
        """
        existing = self._require_credential(credential_id)
        fields = request.model_fields_set

        provider = existing.provider
        if request.provider is not None and "provider" in fields:
            provider = self._require_provider(request.provider).id

        model = existing.model
        if "model" in fields:
            model = (request.model or "").strip() or existing.model

        api_key = existing.api_key
        if "api_key" in fields and (request.api_key or "").strip():
            api_key = (request.api_key or "").strip()

        label = existing.label
        if "label" in fields:
            label = (request.label or "").strip()

        base_url = existing.base_url
        if "base_url" in fields:
            base_url = request.base_url

        row = credential_repo.upsert_credential(
            credential_id=credential_id,
            provider=provider,
            model=model,
            api_key=api_key,
            label=label,
            base_url=base_url,
        )
        logger.info("模型凭据已更新 id=%s provider=%s", credential_id, provider)
        return LlmCredentialResponse(item=self._to_record(row))

    def delete(self, credential_id: str) -> LlmCredentialDeleteResponse:
        """删一条凭据。删掉使用中的那条后不自动改选 —— 由用户在页面上明确选。"""
        deleted = credential_repo.delete_credential(credential_id)
        if not deleted:
            raise AppError("llm.credential_not_found", "模型凭据不存在", status_code=404)
        logger.info("模型凭据已删除 id=%s", credential_id)
        return LlmCredentialDeleteResponse(deleted=True)

    def activate(self, credential_id: str) -> LlmCredentialResponse:
        """把某条设为唯一使用中。"""
        row = credential_repo.set_active(credential_id)
        if row is None:
            raise AppError("llm.credential_not_found", "模型凭据不存在", status_code=404)
        logger.info("模型凭据已启用 id=%s provider=%s", credential_id, row.provider)
        return LlmCredentialResponse(item=self._to_record(row))

    def record_check(self, credential_id: str, *, ok: bool, message: str) -> None:
        """记下最近一次检测结果（页面上要显示「上次检测 3 分钟前 成功」）。"""
        credential_repo.set_check_result(credential_id, ok=ok, message=message)

    def import_from_env(
        self,
        *,
        provider: str,
        model: str,
        base_url: str | None,
        api_key: str,
    ) -> LlmImportEnvResponse:
        """把环境变量里那份配置收编成一条凭据。

        已经存在「同供应商 + 同 key」的凭据时**只回它、不新建**：反复点「从 .env 导入」
        不该攒出一堆一模一样的条目。若当时一条凭据都没有，导入的这条直接生效。
        """
        entry = self._catalog.get(provider)
        existing = credential_repo.find_by_provider_and_key(provider, api_key)
        if existing:
            return LlmImportEnvResponse(
                imported=False,
                item=self._to_record(existing),
                message="环境变量里的这把 key 已经在凭据列表里了",
            )

        credential_id = f"cred-{uuid.uuid4().hex[:12]}"
        # 环境变量里的地址等于供应商默认时不落库，保持「NULL = 跟随默认」这个不变量
        stored_base_url = None if (entry and base_url == entry.base_url) else base_url
        row = credential_repo.upsert_credential(
            credential_id=credential_id,
            provider=provider,
            model=model,
            api_key=api_key,
            label="来自环境变量",
            base_url=stored_base_url,
        )
        if credential_repo.get_active_credential() is None:
            row = credential_repo.set_active(credential_id) or row
        logger.info("已从环境变量导入模型凭据 id=%s provider=%s", credential_id, provider)
        return LlmImportEnvResponse(imported=True, item=self._to_record(row), message="已导入")

    def _require_provider(self, provider_id: str) -> LlmProviderView:
        """校验供应商；不在目录里就报 ``llm.provider_unsupported``。"""
        key = (provider_id or "").strip().lower()
        entry = self._catalog.get(key)
        if entry is None:
            known = " / ".join(sorted(self._catalog))
            raise AppError(
                "llm.provider_unsupported",
                f"不认识的 LLM 供应商 {provider_id or '(空)'}，只支持 {known}",
                status_code=400,
            )
        return entry

    def _require_credential(self, credential_id: str) -> credential_repo.LlmCredentialRow:
        """按 id 取行；不存在就报 404。"""
        row = credential_repo.get_credential(credential_id)
        if row is None:
            raise AppError("llm.credential_not_found", "模型凭据不存在", status_code=404)
        return row

    def _to_record(self, row: credential_repo.LlmCredentialRow) -> LlmCredentialRecord:
        """库行 → 展示记录：补供应商中文名、补默认地址、key 换成掩码。"""
        entry = self._catalog.get(row.provider)
        return LlmCredentialRecord(
            credential_id=row.credential_id,
            provider=row.provider,
            provider_name=entry.name if entry else row.provider,
            label=row.label,
            model=row.model,
            base_url=row.base_url,
            effective_base_url=row.base_url or (entry.base_url if entry else ""),
            api_key_masked=mask_api_key(row.api_key),
            has_api_key=bool(row.api_key.strip()),
            is_active=row.is_active,
            last_check_at=row.last_check_at,
            last_check_ok=row.last_check_ok,
            last_check_message=row.last_check_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
