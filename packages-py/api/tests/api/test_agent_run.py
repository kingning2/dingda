"""Agent 运行入口（临时库 + 假发动机）。

这里测的是**接线口径**，不是发动机逻辑（那在 ``agent/tests/engine/``）：

- 起手必发 ``runStarted``、收尾必发 ``runCompleted`` —— 任何一条路径漏发，
  前端那条消息就永远转圈
- 每帧带 ``id:`` 游标，接回用 ``?after=`` 从日志补齐 —— run 活在请求之外
- 进页面先问活跃探针：有在跑的 run 就接回，而不是当成「上次执行已中断」
- 没有可用模型配置时要说人话（去模型配置页），而不是抛 500
- 发动机自己炸了也要收尾，不能把 SSE 断在半路
- 凭据的参数是**显式**传进 ``resolve_settings`` 的（key / model / base_url），
  不是靠环境变量兜底 —— 那正是「把 DeepSeek 的 key 发到 OpenAI 地址」的来源
- cookie 只从**登录有效**的账号里取
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from agent.llm.models import LlmSettings
from agent.loop import EXIT_OK
from contracts.agent import AgentActiveRunView
from core.errors import AppError
from infrastructure.db import accounts as account_repo
from infrastructure.db import llm_credentials as credential_repo
from infrastructure.db.session import set_db_path

import api.agent_run as agent_run
from api.agent import get_active_agent_run

RUN_URL = "/v1/agent/runtimes/dingda/run"
RESUME_URL = "/v1/agent/runtimes/runs/{run_id}/events"


@pytest.fixture
def agent_db(tmp_path: Path) -> Path:
    """每个用例一个空库。"""
    path = tmp_path / "agent_run.db"
    set_db_path(path)
    return path


@pytest.fixture(autouse=True)
def _clean_running() -> None:
    """``manager`` 是进程级登记表，用例之间必须清干净。"""
    agent_run.manager.reset()
    yield
    agent_run.manager.reset()


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """把模型客户端换成替身：不发请求，但保留 ``settings`` / ``aclose`` 的接口。"""
    client = MagicMock()
    client.settings = LlmSettings(
        provider_id="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="sk-test",
    )
    client.aclose = AsyncMock()
    monkeypatch.setattr(agent_run, "_client_for_run", lambda: client)
    return client


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """把 SSE 文本拆成 ``(事件名, 数据)``。"""
    parsed: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        name = "message"
        data: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        parsed.append((name, data))
    return parsed


def _frame_ids(body: str) -> list[int | None]:
    """每帧 ``id:`` 行的值 —— 断线重连的游标（缺了就报 None）。"""
    ids: list[int | None] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        value: int | None = None
        for line in block.splitlines():
            if line.startswith("id:"):
                value = int(line[3:].strip())
        ids.append(value)
    return ids


def _stub_chat(
    monkeypatch: pytest.MonkeyPatch,
    *,
    events: list[dict[str, Any]] | None = None,
    exit_code: int = EXIT_OK,
    boom: bool = False,
) -> None:
    """把聊天 Workflow 换成替身：发几条事件就返回。

    打在 ``api.agent_run.run_chat`` —— API 只测接线，编排在 ``agent/tests/workflows/``。
    ``boom=True`` 模拟 Workflow 内部已吃掉异常并推 error（与真实 ``run_chat`` 一致）。
    """

    async def fake_run_chat(
        *,
        bus: Any,
        ctx: Any,
        prompt: str,
        platform_hint: str | None = None,
        context_messages: Any = (),
    ) -> int:
        for event in events or []:
            await bus.put(event)
        if boom:
            await bus.error("运行出现意外错误，请重试")
            return 1
        return exit_code

    monkeypatch.setattr(agent_run, "run_chat", fake_run_chat)


def test_run_emits_started_and_completed(
    client: TestClient, agent_db: Path, fake_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """正常一轮：``runStarted`` → 正文 → ``runCompleted``，exitCode 由 Workflow 给。"""
    _stub_chat(monkeypatch, events=[{"type": "textDelta", "text": "找到 3 条"}])

    response = client.post(RUN_URL, json={"prompt": "找露营椅"})
    assert response.status_code == 200
    parsed = _events(response.text)

    assert [name for name, _ in parsed] == ["runStarted", "textDelta", "runCompleted"]
    assert parsed[0][1]["runtimeId"] == "dingda"
    assert parsed[1][1]["text"] == "找到 3 条"
    assert parsed[-1][1]["exitCode"] == EXIT_OK
    assert all(data["runId"] == parsed[0][1]["runId"] for _, data in parsed)
    # 前端只读 data.type，不读 ``event:`` 行 —— 两条必须一致，漏一条事件就丢了
    assert [data["type"] for _, data in parsed] == [name for name, _ in parsed]
    # ``id:`` 行从 1 起、每帧 +1：接回时它就是 ``?after=`` 的游标
    assert _frame_ids(response.text) == [1, 2, 3]


def test_run_id_is_echoed_back(
    client: TestClient, agent_db: Path, fake_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """前端先造 runId 再发请求，后端要按同一个回报。"""
    _stub_chat(monkeypatch)
    parsed = _events(client.post(RUN_URL, json={"prompt": "找货", "run_id": "run-abc"}).text)
    assert parsed[0][1]["runId"] == "run-abc"
    assert parsed[-1][1]["runId"] == "run-abc"


def test_missing_model_config_is_reported_plainly(
    client: TestClient, agent_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """没有可用模型配置：发一条 error + 收尾，而不是 500 或一个断掉的流。"""
    monkeypatch.setattr(
        agent_run,
        "_client_for_run",
        MagicMock(side_effect=AppError("llm.api_key_missing", "没找到 DeepSeek 的 API key")),
    )
    parsed = _events(client.post(RUN_URL, json={"prompt": "找货"}).text)
    assert [name for name, _ in parsed] == ["runStarted", "error", "runCompleted"]
    assert "API key" in parsed[1][1]["message"]
    assert parsed[-1][1]["exitCode"] != EXIT_OK


def test_engine_crash_still_completes(
    client: TestClient, agent_db: Path, fake_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workflow 抛未预期异常：照样发 error 与 ``runCompleted``，SSE 不断在半路。"""
    _stub_chat(monkeypatch, boom=True)
    parsed = _events(client.post(RUN_URL, json={"prompt": "找货"}).text)
    assert [name for name, _ in parsed] == ["runStarted", "error", "runCompleted"]
    assert parsed[-1][1]["exitCode"] != EXIT_OK


def test_resume_replays_only_the_tail(
    client: TestClient, agent_db: Path, fake_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """接回：``?after=N`` 只补 ``seq > N``，且编号还是原来那套（游标能对齐）。

    这条端点是「关掉应用 / 刷新 / 断网之后接回来」的入口 —— run 跑完仍在册
    （TTL 内），所以这里能拿一个已结束的 run 来验重放。
    """
    _stub_chat(
        monkeypatch,
        events=[{"type": "textDelta", "text": "一"}, {"type": "textDelta", "text": "二"}],
    )
    first = client.post(RUN_URL, json={"prompt": "找货", "run_id": "run-1", "work_id": "w1"})
    assert _frame_ids(first.text) == [1, 2, 3, 4]

    resumed = client.get(RESUME_URL.format(run_id="run-1") + "?after=2")
    assert resumed.status_code == 200
    assert [name for name, _ in _events(resumed.text)] == ["textDelta", "runCompleted"]
    assert _frame_ids(resumed.text) == [3, 4]


def test_resume_unknown_run_is_not_found(client: TestClient, agent_db: Path) -> None:
    """查不到的 run 直接 404：客户端该按「上次执行已中断」收尾，而不是干等空流。"""
    assert client.get(RESUME_URL.format(run_id="run-gone")).status_code == 404


def test_resume_without_cursor_replays_from_the_start(
    client: TestClient, agent_db: Path, fake_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """不给 ``after`` 就从 0 整条重放 —— 重进页面时前端重建那条在跑的消息。"""
    _stub_chat(monkeypatch, events=[{"type": "textDelta", "text": "一"}])
    client.post(RUN_URL, json={"prompt": "找货", "run_id": "run-1", "work_id": "w1"})

    resumed = client.get(RESUME_URL.format(run_id="run-1"))
    assert _frame_ids(resumed.text) == [1, 2, 3]


def test_active_run_probe_reports_a_running_run(agent_db: Path) -> None:
    """有在跑的 run 就报出来 —— 客户端据此走接回，而不是「上次执行已中断」。"""

    async def scenario() -> AgentActiveRunView:
        gate = asyncio.Event()

        async def factory(bus: Any, cancel: asyncio.Event) -> int:
            await gate.wait()
            return EXIT_OK

        record = agent_run.manager.start(
            run_id="run-live", runtime_id="dingda", work_id="w1", factory=factory
        )
        view = await get_active_agent_run("w1")
        gate.set()
        await record.task
        return view

    view = asyncio.run(scenario())

    assert view.run_id == "run-live"
    assert view.status == "running"


def test_active_run_probe_is_null_without_one(client: TestClient, agent_db: Path) -> None:
    """没有在跑的 run：``run_id`` 为空 —— 客户端据此走恢复中断那条路。"""
    body = client.get("/v1/agent/works/w1/active-run").json()
    assert body["run_id"] is None
    assert body["work_id"] == "w1"


def test_empty_prompt_is_rejected_before_streaming(
    client: TestClient, agent_db: Path, fake_client: MagicMock
) -> None:
    """空 prompt 直接 400：建一条空消息再让它变红，不如请求就失败。"""
    assert client.post(RUN_URL, json={"prompt": "   "}).status_code == 400


def test_cancel_signals_the_running_run() -> None:
    """取消只通知在跑的那一个；没有对应运行不算失败。"""
    assert agent_run.cancel_run("run-x") is False

    import asyncio

    async def scenario() -> tuple[bool, bool]:
        gate = asyncio.Event()

        async def factory(bus: Any, cancel: asyncio.Event) -> int:
            await gate.wait()
            return EXIT_OK

        record = agent_run.manager.start(
            run_id="run-x", runtime_id="dingda", factory=factory
        )
        signalled = agent_run.cancel_run("run-x")
        seen = record.cancel.is_set()
        gate.set()
        await record.task
        return signalled, seen

    assert asyncio.run(scenario()) == (True, True)
    assert agent_run.cancel_run("run-x") is False, "跑完的 run 不再是可取消的"


def test_cancel_endpoint_accepts_unknown_run(client: TestClient, agent_db: Path) -> None:
    """前端 abort fetch 是另一条取消路径，这里对未知 run 报错只会刷一屏无意义的失败。"""
    body = client.post("/v1/agent/runtimes/runs/run-unknown/cancel").json()
    assert body["ok"] is True
    assert body["signalled"] is False


def test_credential_parameters_are_passed_explicitly(
    agent_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """使用中的凭据要显式传参：key / model 来自库里，base_url 由供应商默认补齐。

    ``base_url`` 留空时必须先补成供应商默认 —— 直接传空会让 ``resolve_settings``
    回落到 ``DINGDA_LLM_BASE_URL``，那就是「页面上选豆包、请求发到 DeepSeek 地址」。
    """
    credential_repo.upsert_credential(
        credential_id="cred-1",
        provider="doubao",
        model="ep-2026",
        api_key="ark-key",
        base_url=None,
    )
    credential_repo.set_active("cred-1")

    box: dict[str, Any] = {}

    def fake_client(settings: Any) -> MagicMock:
        box["settings"] = settings
        return MagicMock()

    monkeypatch.setattr(agent_run, "LlmClient", fake_client)
    agent_run._client_for_run()

    settings = box["settings"]
    assert settings.provider_id == "doubao"
    assert settings.model == "ep-2026"
    assert settings.api_key == "ark-key"
    assert settings.base_url == "https://ark.cn-beijing.volces.com/api/v3"


def test_doubao_coding_plan_credential_uses_coding_endpoint(
    agent_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Coding Plan 凭据要显式落到 /api/coding/v3；这是计费与权限的分界。"""
    credential_repo.upsert_credential(
        credential_id="cred-coding",
        provider="doubao-coding",
        model="doubao-seed-code",
        api_key="ark-coding-key",
        base_url=None,
    )
    credential_repo.set_active("cred-coding")

    box: dict[str, Any] = {}

    def fake_client(settings: Any) -> MagicMock:
        box["settings"] = settings
        return MagicMock()

    monkeypatch.setattr(agent_run, "LlmClient", fake_client)
    agent_run._client_for_run()

    settings = box["settings"]
    assert settings.provider_id == "doubao-coding"
    assert settings.base_url == "https://ark.cn-beijing.volces.com/api/coding/v3"


def test_credential_without_active_falls_back_to_env(
    agent_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """一条凭据都没有时走环境变量：``.env`` 是仓库既有的配置方式，不为新页面废掉它。

    这里只验「回落到了 ``from_env()`` 且一个参数都没传」—— 传了参数就等于用某个
    默认值盖掉环境，那才是「页面上没配、却按别的配置在跑」。三级优先级本身由
    ``resolve_settings`` 负责，在 ``tests/llm/test_providers.py`` 里测。
    """
    fallback = MagicMock()
    patched = MagicMock()
    patched.from_env.return_value = fallback
    monkeypatch.setattr(agent_run, "LlmClient", patched)

    assert agent_run._client_for_run() is fallback
    patched.from_env.assert_called_once_with()


def test_cookie_resolver_skips_invalid_accounts(agent_db: Path) -> None:
    """cookie 只从登录有效的账号里取；没有就返回 None，由平台页去报登录态。"""
    account_repo.upsert_account(
        account_id="a-old",
        platform="xianyu",
        display_name="过期号",
        cookie="expired=1",
        auth_valid=False,
    )
    assert agent_run._resolve_cookie("xianyu") is None

    account_repo.upsert_account(
        account_id="a-ok",
        platform="xianyu",
        display_name="正常号",
        cookie="ok=1",
        auth_valid=True,
    )
    assert agent_run._resolve_cookie("xianyu") == "ok=1"
    assert agent_run._resolve_cookie("xiaohongshu") is None


def test_cookie_resolver_honours_an_explicit_account(agent_db: Path) -> None:
    """指定账号时按 id 取，不走「平台第一个有效账号」那条分支。"""
    account_repo.upsert_account(
        account_id="a-2",
        platform="xianyu",
        display_name="小号",
        cookie="second=1",
        auth_valid=True,
    )
    assert agent_run._resolve_cookie("xianyu", "a-2") == "second=1"
    assert agent_run._resolve_cookie("xianyu", "a-missing") is None
