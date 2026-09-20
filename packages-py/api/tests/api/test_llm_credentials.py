"""模型配置 HTTP 端点（临时库）。

这里测的是**契约与口径**，不是 SQL：key 只进不出、供应商必须在校目录里、
同一时间只有一条使用中、改凭据时不给 key 就不该动 key、探活与拉模型列表失败要回
``llm.*`` 精确错误码而不是一句「请求失败」。

探活与拉模型列表都走 mock：真打供应商的用例既慢又需要 key，属集成测试范畴，不进这里。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from agent.llm.models import ChatResult
from core.errors import AppError
from infrastructure.db.session import set_db_path

RAW_KEY = "sk-abcdef123456"


@pytest.fixture
def llm_client(tmp_path: Path, client: TestClient) -> TestClient:
    """每个用例一个空库；表在首次连接时由 repo 自己建。"""
    set_db_path(tmp_path / "llm.db")
    return client


def _create(
    client: TestClient,
    *,
    provider: str = "deepseek",
    api_key: str = RAW_KEY,
    **extra: Any,
) -> Any:
    return client.post(
        "/v1/llm/credentials",
        json={"provider": provider, "api_key": api_key, **extra},
    )


def _patch_probe(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: ChatResult | None = None,
    error: AppError | None = None,
) -> dict[str, Any]:
    """把探活用的 ``LlmClient`` 换成假的；返回能读到实际连接参数的盒子。"""
    box: dict[str, Any] = {}
    fake = MagicMock()
    fake.chat = AsyncMock(side_effect=error) if error else AsyncMock(return_value=result)
    fake.aclose = AsyncMock()

    def _factory(settings: Any) -> MagicMock:
        box["settings"] = settings
        return fake

    monkeypatch.setattr("api.llm.LlmClient", _factory)
    return box


def test_providers_catalog_marks_doubao_as_requiring_model(llm_client: TestClient) -> None:
    """豆包没有默认模型，前端必须把它标成必填 —— 这个标志由目录推出，不写死。"""
    body = llm_client.get("/v1/llm/providers").json()
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["deepseek"]["default_model"] == "deepseek-flash"
    assert by_id["deepseek"]["requires_model"] is False
    assert by_id["doubao"]["requires_model"] is True


def test_doubao_coding_plan_has_coding_base_url(llm_client: TestClient) -> None:
    """Coding Plan 是独立计费域；默认地址必须带 /api/coding/v3，不能让用户手改。"""
    providers = llm_client.get("/v1/llm/providers").json()["items"]
    coding = next(item for item in providers if item["id"] == "doubao-coding")

    assert coding["name"] == "豆包 Coding Plan"
    assert coding["base_url"] == "https://ark.cn-beijing.volces.com/api/coding/v3"
    assert coding["requires_model"] is True


def test_credentials_start_empty(llm_client: TestClient) -> None:
    body = llm_client.get("/v1/llm/credentials").json()
    assert body["items"] == []
    assert body["active_id"] is None


def test_create_credential_masks_key_and_activates(llm_client: TestClient) -> None:
    """新建的响应里**不能**出现 key 原文，且第一条默认生效、地址回落到供应商默认。"""
    response = _create(llm_client, label="主号")
    assert response.status_code == 200
    assert RAW_KEY not in response.text

    item = response.json()["item"]
    assert item["api_key_masked"] == "sk-abc****3456"
    assert item["has_api_key"] is True
    assert item["is_active"] is True
    assert item["provider_name"] == "DeepSeek"
    assert item["model"] == "deepseek-flash"
    assert item["base_url"] is None
    assert item["effective_base_url"] == "https://api.deepseek.com"

    listed = llm_client.get("/v1/llm/credentials").json()
    assert listed["active_id"] == item["credential_id"]


def test_create_without_key_is_rejected(llm_client: TestClient) -> None:
    response = _create(llm_client, api_key="   ")
    assert response.status_code == 400
    assert response.json()["code"] == "llm.api_key_missing"


def test_unknown_provider_is_rejected(llm_client: TestClient) -> None:
    response = _create(llm_client, provider="openai")
    assert response.status_code == 400
    assert response.json()["code"] == "llm.provider_unsupported"


def test_doubao_requires_explicit_model(llm_client: TestClient) -> None:
    """豆包只认 ``ep-`` 接入点 ID，没填就该在入口被挡下，而不是等到调用时 404。"""
    response = _create(llm_client, provider="doubao", api_key="ark-key-123456")
    assert response.status_code == 400
    assert response.json()["code"] == "llm.model_required"

    ok = _create(llm_client, provider="doubao", api_key="ark-key-123456", model="ep-2026")
    assert ok.status_code == 200
    assert ok.json()["item"]["model"] == "ep-2026"


def test_doubao_coding_plan_uses_coding_endpoint(llm_client: TestClient) -> None:
    """Coding Plan 凭据不填地址时也必须落到 coding 域，而不是普通推理域。"""
    response = _create(
        llm_client,
        provider="doubao-coding",
        api_key="ark-coding-key-123456",
        model="doubao-seed-code",
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["provider_name"] == "豆包 Coding Plan"
    assert item["base_url"] is None
    assert item["effective_base_url"] == "https://ark.cn-beijing.volces.com/api/coding/v3"


def test_activate_keeps_only_one_active(llm_client: TestClient) -> None:
    first = _create(llm_client, label="主号").json()["item"]
    second = _create(llm_client, api_key="sk-zzzz999999", label="备用").json()["item"]

    assert llm_client.post(f"/v1/llm/credentials/{second['credential_id']}/activate").status_code == 200

    items = llm_client.get("/v1/llm/credentials").json()["items"]
    active = [item["credential_id"] for item in items if item["is_active"]]
    assert active == [second["credential_id"]]
    assert next(item for item in items if item["credential_id"] == first["credential_id"])["is_active"] is False


def test_update_without_key_keeps_existing_key(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """改备注名时不给 key，落库的必须还是原文 —— 否则一次改名就把 key 改成掩码了。"""
    created = _create(llm_client).json()["item"]
    updated = llm_client.put(
        f"/v1/llm/credentials/{created['credential_id']}",
        json={"label": "改过名"},
    ).json()["item"]
    assert updated["label"] == "改过名"
    assert updated["api_key_masked"] == created["api_key_masked"]

    box = _patch_probe(monkeypatch, result=ChatResult(text="pong", model="deepseek-flash"))
    llm_client.post(f"/v1/llm/credentials/{created['credential_id']}/test")
    assert box["settings"].api_key == RAW_KEY


def test_update_base_url_null_restores_provider_default(llm_client: TestClient) -> None:
    """``base_url`` 出现且为 null = 恢复默认；字段不出现 = 不改。这两者必须分得开。"""
    created = _create(llm_client, base_url="https://proxy.example.com/v1").json()["item"]
    assert created["effective_base_url"] == "https://proxy.example.com/v1"

    renamed = llm_client.put(
        f"/v1/llm/credentials/{created['credential_id']}",
        json={"label": "只改名"},
    ).json()["item"]
    assert renamed["base_url"] == "https://proxy.example.com/v1"

    cleared = llm_client.put(
        f"/v1/llm/credentials/{created['credential_id']}",
        json={"base_url": None},
    ).json()["item"]
    assert cleared["base_url"] is None
    assert cleared["effective_base_url"] == "https://api.deepseek.com"


def test_delete_credential_then_missing(llm_client: TestClient) -> None:
    created = _create(llm_client).json()["item"]
    assert llm_client.delete(f"/v1/llm/credentials/{created['credential_id']}").json()["deleted"] is True
    assert llm_client.delete(f"/v1/llm/credentials/{created['credential_id']}").status_code == 404
    assert llm_client.put("/v1/llm/credentials/cred-missing", json={"label": "x"}).status_code == 404
    assert llm_client.post("/v1/llm/credentials/cred-missing/activate").status_code == 404


def test_import_env_without_config_reports_not_imported(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """环境里没配不是错误：探测空手而归也要回 200，前端据此决定要不要显示按钮。"""
    for name in ("DINGDA_LLM_PROVIDER", "DINGDA_LLM_MODEL", "DINGDA_LLM_BASE_URL",
                 "DINGDA_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "ARK_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    body = llm_client.post("/v1/llm/credentials/import-env").json()
    assert body["imported"] is False
    assert "环境变量" in body["message"]


def test_import_env_collects_config_and_is_idempotent(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DINGDA_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DINGDA_LLM_MODEL", "deepseek-flash")
    monkeypatch.setenv("DINGDA_LLM_API_KEY", RAW_KEY)

    first = llm_client.post("/v1/llm/credentials/import-env").json()
    assert first["imported"] is True
    assert first["item"]["is_active"] is True
    # 环境里的地址就是供应商默认 → 不落库，保持「NULL = 跟随默认」的不变量
    assert first["item"]["base_url"] is None

    again = llm_client.post("/v1/llm/credentials/import-env").json()
    assert again["imported"] is False
    assert again["item"]["credential_id"] == first["item"]["credential_id"]
    assert len(llm_client.get("/v1/llm/credentials").json()["items"]) == 1


def test_probe_failure_reports_precise_code(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """探活失败回 200 + ``check.ok=false``：这是业务结果，不是 HTTP 层错误。"""
    created = _create(llm_client).json()["item"]
    _patch_probe(
        monkeypatch,
        error=AppError("llm.auth_failed", "API key 无效或已过期", status_code=401),
    )

    response = llm_client.post(f"/v1/llm/credentials/{created['credential_id']}/test")
    assert response.status_code == 200
    check = response.json()["check"]
    assert check["ok"] is False
    assert check["code"] == "llm.auth_failed"
    assert check["message"] == "API key 无效或已过期"

    stored = llm_client.get("/v1/llm/credentials").json()["items"][0]
    assert stored["last_check_ok"] is False
    assert stored["last_check_message"] == "API key 无效或已过期"
    assert stored["last_check_at"] is not None


def test_probe_success_records_latency(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _create(llm_client).json()["item"]
    box = _patch_probe(monkeypatch, result=ChatResult(text="  pong  ", model="deepseek-flash"))

    check = llm_client.post(f"/v1/llm/credentials/{created['credential_id']}/test").json()["check"]
    assert check["ok"] is True
    assert check["latency_ms"] is not None
    assert check["reply"] == "pong"
    assert check["model"] == "deepseek-flash"
    assert box["settings"].timeout_s == 20.0
    assert box["settings"].max_retries == 0

    stored = llm_client.get("/v1/llm/credentials").json()["items"][0]
    assert stored["last_check_ok"] is True


def test_probe_uses_provider_default_when_base_url_blank(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """页面显示 ``effective_base_url``、实际请求也必须打同一个地址，不能各算各的。"""
    created = _create(llm_client).json()["item"]
    box = _patch_probe(monkeypatch, result=ChatResult(text="pong"))
    llm_client.post(f"/v1/llm/credentials/{created['credential_id']}/test")
    assert box["settings"].base_url == created["effective_base_url"]


# --------------------------------------------------------------------------- 模型列表


def _patch_models(
    monkeypatch: pytest.MonkeyPatch,
    *,
    models: list[str] | None = None,
    error: AppError | None = None,
) -> dict[str, Any]:
    """把拉模型列表用的 ``LlmClient`` 换成假的；返回能读到实际连接参数的盒子。"""
    box: dict[str, Any] = {}
    fake = MagicMock()
    fake.list_models = AsyncMock(side_effect=error) if error else AsyncMock(return_value=models or [])
    fake.aclose = AsyncMock()

    def _factory(settings: Any) -> MagicMock:
        box["settings"] = settings
        box["fake"] = fake
        return fake

    monkeypatch.setattr("api.llm.LlmClient", _factory)
    return box


def test_models_endpoint_lists_and_carries_catalog_default(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """表单态拉列表：凭据还没保存，只凭一把 key 就该能拿到卡片数据。

    连接参数必须是「短超时 + 不重试」——用户盯着按钮等，60 秒的默认值体验太差。
    """
    box = _patch_models(monkeypatch, models=["deepseek-chat", "deepseek-reasoner"])

    response = llm_client.post(
        "/v1/llm/models",
        json={"provider": "deepseek", "api_key": RAW_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["provider"] == "deepseek"
    assert body["models"] == ["deepseek-chat", "deepseek-reasoner"]
    # 卡片上的「默认」徽章靠这个字段，不能靠前端再猜一遍目录
    assert body["default_model"] == "deepseek-flash"
    assert body["current_model"] is None
    assert body["message"] is None

    assert box["settings"].base_url == "https://api.deepseek.com"
    assert box["settings"].timeout_s == 20.0
    assert box["settings"].max_retries == 0
    box["fake"].aclose.assert_awaited()


def test_models_endpoint_honors_custom_base_url(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """填了中转地址就打中转：拉列表和正式调用必须打同一个地址，否则列表是一套、跑起来是另一套。"""
    box = _patch_models(monkeypatch, models=["m1"])

    llm_client.post(
        "/v1/llm/models",
        json={"provider": "deepseek", "api_key": RAW_KEY, "base_url": " https://proxy.example.com/v1 "},
    )
    assert box["settings"].base_url == "https://proxy.example.com/v1"


def test_models_endpoint_blank_base_url_falls_back_to_catalog(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``base_url`` 传空串等于没传 —— 空串原样透下去会拼出 ``/chat/completions`` 这种相对地址。"""
    box = _patch_models(monkeypatch, models=["m1"])

    llm_client.post("/v1/llm/models", json={"provider": "deepseek", "api_key": RAW_KEY, "base_url": "   "})
    assert box["settings"].base_url == "https://api.deepseek.com"


def test_models_endpoint_failure_is_200_with_reason(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拉不到回 200 + ``ok=false``：这是业务结果，不是 HTTP 层错误。

    回 4xx 会让前端既弹错误框、又收一份结果，两条路径说同一件事。
    """
    _patch_models(
        monkeypatch,
        error=AppError("llm.auth_failed", "API key 无效或已过期", status_code=401),
    )

    response = llm_client.post("/v1/llm/models", json={"provider": "deepseek", "api_key": RAW_KEY})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["message"] == "API key 无效或已过期"
    assert body["models"] == []
    # 失败也要带目录默认模型：前端这时退回手填框，用它预填比留空好
    assert body["default_model"] == "deepseek-flash"


def test_models_endpoint_empty_list_promises_manual_input(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """空列表**不是**错误：有的网关就是不给列表（方舟只认 ``ep-`` 接入点）。

    这时文案必须明说可以手填 —— 否则用户以为 key 填错了，反复重试一把本来好使的 key。
    """
    _patch_models(monkeypatch, models=[])

    body = llm_client.post("/v1/llm/models", json={"provider": "doubao", "api_key": "ark-key-1"}).json()
    assert body["ok"] is True
    assert body["models"] == []
    assert "手动填写" in (body["message"] or "")


def test_models_endpoint_rejects_unknown_provider(llm_client: TestClient) -> None:
    """供应商不在目录里就是 400：目录是供应商事实的唯一来源，不接受自创 id。"""
    response = llm_client.post("/v1/llm/models", json={"provider": "openai", "api_key": RAW_KEY})
    assert response.status_code == 400
    assert response.json()["code"] == "llm.provider_unsupported"


def test_credential_models_uses_stored_key(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """编辑态走这条：key 只回掩码，浏览器里根本没有原文，只能用库里那把。

    ``current_model`` 必须回 —— 前端据此把当前那张卡片标成已选中。
    """
    created = _create(llm_client, model="deepseek-chat", label="主号").json()["item"]
    box = _patch_models(monkeypatch, models=["deepseek-chat", "deepseek-reasoner"])

    body = llm_client.get(f"/v1/llm/credentials/{created['credential_id']}/models").json()
    assert body["ok"] is True
    assert body["provider"] == "deepseek"
    assert body["models"] == ["deepseek-chat", "deepseek-reasoner"]
    assert body["current_model"] == "deepseek-chat"
    assert box["settings"].api_key == RAW_KEY


def test_credential_models_failure_keeps_current_model(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拉失败也要回 ``current_model``：手填框得知道原来填的是什么，不能变回空。"""
    created = _create(llm_client, model="deepseek-chat").json()["item"]
    _patch_models(
        monkeypatch,
        error=AppError("llm.rate_limited", "上游限流，请稍后重试", status_code=429),
    )

    response = llm_client.get(f"/v1/llm/credentials/{created['credential_id']}/models")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["message"] == "上游限流，请稍后重试"
    assert body["current_model"] == "deepseek-chat"
    assert body["default_model"] == "deepseek-flash"


def test_credential_models_missing_credential_is_404(llm_client: TestClient) -> None:
    assert llm_client.get("/v1/llm/credentials/cred-missing/models").status_code == 404
