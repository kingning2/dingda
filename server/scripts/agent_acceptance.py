"""叮答外部 Agent 端到端验收脚本。

职责：
    真实启动一个临时 FastAPI 实例，通过 SSE 调用 OpenCode，
    验证浏览器直播、上下文切换、Skill/历史压缩，以及前端历史回退逻辑。

设计说明：
    - OpenCode 使用 ``openrouter/tencent/hy3``。
    - 不 mock Agent、不 mock Crawler；真实失败保留事件摘要
    - 失败会归因成「本机代理配置错误」或「Agent 链路失败」，见 ``_classify_failure``
    - 服务器在后台线程启动，脚本结束时关闭

使用示例：
    uv run python scripts/agent_acceptance.py --case compression --case rollback
    uv run python scripts/agent_acceptance.py --case preview
    uv run python scripts/agent_acceptance.py --case context
    uv run python scripts/agent_acceptance.py --case proxy   # 代理 vs 链路归因
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import httpx
import uvicorn

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT_DIR / "server"
ROLLBACK_SCRIPT = ROOT_DIR / "scripts" / "agent-rollback-check.mjs"
# 大小写都要看：Node / undici 认小写，curl 类工具认大写
_PROXY_URL_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
# 本机回环必须绕开代理，否则验收脚本自己的 SSE 也会被坏代理带死
_NO_PROXY_VALUE = "127.0.0.1,localhost,::1"
# 连接类故障特征：命中即说明卡在网络 / 代理层，不是 Agent 链路本身
_CONNECT_SYMPTOM = re.compile(
    r"cannot connect to api|unable to connect|is the computer able to access"
    r"|econnrefused|econnreset|enotfound|etimedout|eai_again|socket hang up"
    r"|fetch failed|proxy|tunnel|network is unreachable|connection refused",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeTarget:
    """一组外部 Agent / 模型组合。"""

    runtime_id: str
    model_id: str


@dataclass
class CheckResult:
    """单项验收结果。"""

    name: str
    ok: bool
    details: dict[str, Any]


def _free_port() -> int:
    """取一个本机空闲端口。"""
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _proxy_problem(value: str) -> str | None:
    """畸形代理 URL 的原因；正常返回 None。

    只判断「会不会把网络带死」，不判连通性：``http://1270.0.01:7897`` 这类非法
    IPv4 会让 Node / httpx 直接建不出连接，而合法代理（哪怕不通）不算畸形。
    """
    text = (value or "").strip()
    if not text:
        return None
    candidate = text if "://" in text else f"http://{text}"
    try:
        parsed = urllib.parse.urlsplit(candidate)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        return f"URL 无法解析：{exc}"
    if not host:
        return "缺少主机名"
    if re.fullmatch(r"[0-9.]+", host):
        octets = host.split(".")
        if len(octets) != 4 or any(
            not part.isdigit() or int(part) > 255 for part in octets
        ):
            return f"非法 IPv4：{host}"
    if port is not None and not 0 < port < 65536:
        return f"非法端口：{port}"
    return None


def _detect_proxy_problems() -> list[dict[str, str]]:
    """当前环境里所有会把 Agent 网络带死的代理变量。"""
    problems: list[dict[str, str]] = []
    for key in _PROXY_URL_KEYS:
        value = os.environ.get(key, "").strip()
        if not value:
            continue
        reason = _proxy_problem(value)
        if reason:
            problems.append({"key": key, "value": value, "reason": reason})
    return problems


def _allow_loopback_through_proxy() -> None:
    """让本机回环绕开代理：验收脚本自己打 Server 的 SSE 不能被坏代理带死。"""
    parts = [
        os.environ.get("NO_PROXY", "").strip(),
        _NO_PROXY_VALUE,
    ]
    merged = ",".join(dict.fromkeys(p for chunk in parts for p in chunk.split(",") if p.strip()))
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


def _sanitize_proxy_env() -> list[dict[str, str]]:
    """放行本机回环并清掉畸形代理变量，返回被清掉的变量。"""
    _allow_loopback_through_proxy()
    removed = _detect_proxy_problems()
    for row in removed:
        os.environ.pop(row["key"], None)
    return removed


def _classify_failure(
    error_text: str,
    *,
    proxy_problems: list[dict[str, str]],
) -> str:
    """把一次失败归成「本机代理配置错误」或「Agent 链路失败」。

    连接类报错 + 环境里确有畸形代理 → ``proxy-misconfigured``；
    同样报错但环境干净 → ``network-unreachable``（是网络，不是代理配置写错）；
    其余 → ``agent-chain``（链路自身的问题）。
    """
    text = (error_text or "").strip()
    if not text:
        return "no-error-text"
    if _CONNECT_SYMPTOM.search(text):
        return "proxy-misconfigured" if proxy_problems else "network-unreachable"
    return "agent-chain"


def _wait_for_server(api_base: str, timeout_s: float = 30.0) -> None:
    """等待临时 Server 返回健康状态。"""
    deadline = time.monotonic() + timeout_s
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{api_base}/v1/runtime/status", timeout=1.5)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"Server 启动超时：{last_error}")


@contextlib.contextmanager
def _serve(host: str = "127.0.0.1", port: int | None = None) -> Iterator[str]:
    """在后台线程启动真实 FastAPI，并返回 API Base。"""
    actual_port = port or _free_port()
    api_base = f"http://{host}:{actual_port}"
    os.environ["DINGDA_HEADROOM"] = "1"
    os.environ["DINGDA_API_BASE"] = api_base

    from src.app import create_app
    from src.core.config import Settings

    settings = Settings.from_env(
        host=host,
        port=actual_port,
        log_level="WARNING",
        reload=False,
    )
    config = uvicorn.Config(
        create_app(settings),
        host=host,
        port=actual_port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, name="agent-acceptance-server", daemon=True)
    thread.start()
    try:
        _wait_for_server(api_base)
        yield api_base
    finally:
        server.should_exit = True
        thread.join(timeout=15)


async def _run_runtime(
    api_base: str,
    target: RuntimeTarget,
    prompt: str,
    *,
    cwd: Path,
    context_messages: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    timeout_s: float = 300.0,
) -> list[dict[str, Any]]:
    """调用一次外部 Agent SSE，并返回全部结构化事件。"""
    run_id = f"accept-{target.runtime_id}-{uuid.uuid4().hex[:8]}"
    body = {
        "prompt": prompt,
        "run_id": run_id,
        "cwd": str(cwd),
        "model_id": target.model_id,
        "session_id": session_id,
        "context_messages": context_messages,
    }
    events: list[dict[str, Any]] = []
    timeout = httpx.Timeout(timeout_s, connect=15.0, read=timeout_s, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{api_base}/v1/agent/runtimes/{target.runtime_id}/run",
            json=body,
            headers={"Accept": "text/event-stream"},
        ) as response:
            if response.status_code >= 400:
                text = (await response.aread()).decode("utf-8", "replace")
                raise RuntimeError(f"HTTP {response.status_code}: {text[:500]}")
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    payload = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    events.append(payload)
    return events


def _assistant_text(events: list[dict[str, Any]]) -> str:
    """拼出一轮 Agent 的正文输出。"""
    return "".join(
        str(event.get("text") or "")
        for event in events
        if event.get("type") == "textDelta"
    ).strip()


def _event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """把 Agent 事件压成便于报告的摘要。"""
    frames = [event for event in events if event.get("type") == "browserFrame"]
    errors = [str(event.get("message") or "") for event in events if event.get("type") == "error"]
    return {
        "event_count": len(events),
        "text": _assistant_text(events)[:500],
        "frame_count": len(frames),
        "frame_urls": [str(event.get("url") or "") for event in frames][:8],
        "tool_calls": [
            str(event.get("name") or "")
            for event in events
            if event.get("type") == "toolCall"
        ][:12],
        "errors": errors,
        "completed": any(event.get("type") == "runCompleted" for event in events),
    }


def _target_row(
    target: RuntimeTarget,
    events: list[dict[str, Any]],
    *,
    proxy_problems: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """一次 runtime 运行的事件摘要；有报错时顺带归因到代理或链路。"""
    row = _event_summary(events)
    row["runtime_id"] = target.runtime_id
    row["model_id"] = target.model_id
    if row.get("errors"):
        problems = _detect_proxy_problems() if proxy_problems is None else proxy_problems
        row["failure_kind"] = _classify_failure(" ".join(row["errors"]), proxy_problems=problems)
    return row


def _error_row(
    target: RuntimeTarget,
    exc: BaseException,
    *,
    proxy_problems: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """调用本身抛错（连不上 Server 等）时的归因行。"""
    problems = _detect_proxy_problems() if proxy_problems is None else proxy_problems
    return {
        "runtime_id": target.runtime_id,
        "model_id": target.model_id,
        "error": str(exc),
        "failure_kind": _classify_failure(str(exc), proxy_problems=problems),
    }


def _check_compression() -> CheckResult:
    """验证 Skill 注入和换 Agent 历史都经过 Headroom。"""
    from src.cli.prompts import compose_agent_prompt
    from src.tools.skill import SKILLS_CWD_ALIAS

    logger = logging.getLogger("dingda.agent.compress")
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    capture = _Capture()
    old_level = logger.level
    logger.addHandler(capture)
    logger.setLevel(logging.INFO)
    try:
        with tempfile.TemporaryDirectory(prefix="dingda-agent-compress-") as temp:
            workdir = Path(temp)
            prompt = compose_agent_prompt(
                "继续处理",
                workdir=workdir,
                context_messages=[
                    {"role": "user", "content": "先记住商品编号 731。"},
                    {"role": "assistant", "content": "已记住 731。"},
                ],
            )
            staged_skill = workdir / SKILLS_CWD_ALIAS / "dingda-crawl" / "SKILL.md"
            compressed = [row for row in records if "headroom compress saved=" in row]
            tokens = []
            for row in compressed:
                match = re.search(r"saved=(\d+) before=(\d+) after=(\d+)", row)
                if match:
                    tokens.append(tuple(int(value) for value in match.groups()))
            total_saved = sum(row[0] for row in tokens)
            return CheckResult(
                name="compression",
                ok=len(compressed) >= 2 and staged_skill.is_file(),
                details={
                    "compress_calls": len(compressed),
                    "tokens": tokens,
                    "tokens_before_total": sum(row[1] for row in tokens),
                    "tokens_after_total": sum(row[2] for row in tokens),
                    "total_saved": total_saved,
                    # 调用成功 ≠ 真的压掉了：0 节省说明链路通了但压缩没生效
                    "effective": total_saved > 0,
                    "note": (
                        "headroom 已调用且确有节省"
                        if total_saved > 0
                        else "headroom 已调用但 0 节省：Kompress 模型未就绪时退化为本地去重，"
                        "非冗余文本压不动（需 headroom-ai[ml] 并预热）"
                    ),
                    "prompt_chars": len(prompt),
                    "staged_skill": str(staged_skill),
                },
            )
    finally:
        logger.removeHandler(capture)
        logger.setLevel(old_level)


def _check_rollback() -> CheckResult:
    """调用 Node + Vite，验证真实前端回退函数。"""
    node = shutil.which("node")
    if not node:
        return CheckResult(name="rollback", ok=False, details={"error": "node not found"})
    proc = subprocess.run(
        [node, str(ROLLBACK_SCRIPT)],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    payload: dict[str, Any] = {}
    for line in reversed((proc.stdout or "").splitlines()):
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    return CheckResult(
        name="rollback",
        ok=proc.returncode == 0 and payload.get("ok") is True,
        details={
            **payload,
            "stderr": (proc.stderr or "").strip()[-1000:],
        },
    )


async def _check_preview(api_base: str, targets: list[RuntimeTarget], timeout_s: float) -> CheckResult:
    """验证外部 Agent 调 preview 时 browserFrame 能到 SSE。"""
    rows: list[dict[str, Any]] = []
    for target in targets:
        with tempfile.TemporaryDirectory(prefix=f"dingda-{target.runtime_id}-live-") as temp:
            try:
                events = await _run_runtime(
                    api_base,
                    target,
                    (
                        "这是直播链路验收。必须真实调用 dingda-crawl 的 preview 能力，"
                        "打开 https://example.com/；不要只描述步骤，不要调用其他工具。"
                        "完成后只回复 PREVIEW_OK。"
                    ),
                    cwd=Path(temp),
                    timeout_s=timeout_s,
                )
                summary = _target_row(target, events)
            except Exception as exc:  # noqa: BLE001
                summary = _error_row(target, exc)
            rows.append(summary)
    ok = all(
        row.get("completed") is True
        and int(row.get("frame_count") or 0) > 0
        and any(str(url).startswith("https://example.com") for url in row.get("frame_urls") or [])
        for row in rows
    )
    return CheckResult(name="browser-live-preview", ok=ok, details={"targets": rows})


async def _check_search(api_base: str, targets: list[RuntimeTarget], timeout_s: float) -> CheckResult:
    """验证浏览器搜索工具能产生真实直播帧。"""
    rows: list[dict[str, Any]] = []
    for target in targets:
        with tempfile.TemporaryDirectory(prefix=f"dingda-{target.runtime_id}-search-") as temp:
            try:
                events = await _run_runtime(
                    api_base,
                    target,
                    (
                        "必须真实调用 dingda-crawl 的 search 能力："
                        "platform=xiaohongshu，query=露营椅，limit=2。"
                        "不要只说明步骤，不要编造结果。完成后只回复 SEARCH_OK。"
                    ),
                    cwd=Path(temp),
                    timeout_s=timeout_s,
                )
                summary = _target_row(target, events)
            except Exception as exc:  # noqa: BLE001
                summary = _error_row(target, exc)
            rows.append(summary)
    ok = all(
        row.get("completed") is True
        and int(row.get("frame_count") or 0) > 0
        and any("xiaohongshu.com" in str(url) for url in row.get("frame_urls") or [])
        and any("run_tool.py" in str(name) or "Bash" in str(name) for name in row.get("tool_calls") or [])
        for row in rows
    )
    return CheckResult(name="browser-live-search", ok=ok, details={"targets": rows})


async def _check_context_switch(
    api_base: str,
    targets: list[RuntimeTarget],
    timeout_s: float,
) -> CheckResult:
    """验证切换 Agent 时，叮答历史压缩后仍能承接上下文。"""
    if len(targets) < 2:
        return CheckResult(name="context-switch", ok=False, details={"error": "need at least 2 runtimes"})

    rows: list[dict[str, Any]] = []
    pairs = ((targets[0], targets[1], "731"), (targets[1], targets[0], "842"))
    for source, target, code in pairs:
        prime_prompt = f"只记住暗号 {code}，不要调用工具。完成后回复“已记住”。"
        switch_prompt = "暗号是多少？只回复数字。"
        with tempfile.TemporaryDirectory(prefix="dingda-agent-context-") as temp:
            cwd = Path(temp)
            try:
                first_events = await _run_runtime(
                    api_base,
                    source,
                    prime_prompt,
                    cwd=cwd,
                    timeout_s=timeout_s,
                )
                first_text = _assistant_text(first_events)
                context_messages = [
                    {"role": "user", "content": prime_prompt[:2000]},
                    {"role": "assistant", "content": first_text[:2000]},
                ]
                second_events = await _run_runtime(
                    api_base,
                    target,
                    switch_prompt,
                    cwd=cwd,
                    context_messages=context_messages,
                    timeout_s=timeout_s,
                )
                second_text = _assistant_text(second_events)
                rows.append(
                    {
                        "source": source.runtime_id,
                        "target": target.runtime_id,
                        "expected": code,
                        "first_text": first_text[:120],
                        "second_text": second_text[:120],
                        "ok": code in second_text,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    {
                        "source": source.runtime_id,
                        "target": target.runtime_id,
                        "expected": code,
                        "error": str(exc),
                        "failure_kind": _classify_failure(
                            str(exc), proxy_problems=_detect_proxy_problems()
                        ),
                        "ok": False,
                    }
                )
    return CheckResult(name="context-switch", ok=all(row.get("ok") for row in rows), details={"pairs": rows})


async def _probe_target(
    api_base: str,
    target: RuntimeTarget,
    prompt: str,
    cwd: Path,
    timeout_s: float,
    proxy_problems: list[dict[str, str]],
    stage: str,
) -> dict[str, Any]:
    """跑一轮探针，标注阶段、成败与失败归因。"""
    try:
        events = await _run_runtime(api_base, target, prompt, cwd=cwd, timeout_s=timeout_s)
        row = _target_row(target, events, proxy_problems=proxy_problems)
    except Exception as exc:  # noqa: BLE001
        row = _error_row(target, exc, proxy_problems=proxy_problems)
    row["stage"] = stage
    # runCompleted 恒为真（CLI 退出即补发），成败要看有没有 error 事件
    row["ok"] = bool(row.get("completed")) and not row.get("errors")
    return row


def _proxy_verdict(dirty: dict[str, Any], clean_ok: bool) -> str:
    """把两轮结果收成一句结论。"""
    if clean_ok and not dirty.get("ok"):
        return "proxy-misconfigured"  # 坏代理带死、清掉即好：本机代理配置错误
    if clean_ok:
        return "agent-chain-ok"  # 两轮都过：代理与链路都没问题
    return "model-or-chain-unreachable"  # 清掉代理仍失败：不是代理配置问题


async def _check_proxy(
    api_base: str,
    target: RuntimeTarget,
    timeout_s: float,
) -> CheckResult:
    """区分「本机代理配置错误」和「Agent 链路失败」。

    同一个 runtime 跑两轮：
        1. 强制注入畸形代理 ``http://1270.0.01:7897`` —— 应当失败，且归因为代理问题
        2. 清掉代理 —— 应当成功，证明模型可达、Agent 链路完好

    判定依据是第二轮：清掉代理仍失败，就说明问题在模型或链路本身，不是代理配置。
    """
    prompt = "只回复 PONG 这一个词。不要调用任何工具。"
    dirty_proxy = "http://1270.0.01:7897"
    snapshot = {
        key: os.environ.get(key) for key in (*_PROXY_URL_KEYS, "NO_PROXY", "no_proxy")
    }
    stages: list[dict[str, Any]] = []
    try:
        with tempfile.TemporaryDirectory(prefix=f"dingda-{target.runtime_id}-proxy-") as temp:
            cwd = Path(temp)
            for key in _PROXY_URL_KEYS:
                os.environ[key] = dirty_proxy
            _allow_loopback_through_proxy()
            dirty_problems = _detect_proxy_problems()
            stages.append(
                await _probe_target(
                    api_base, target, prompt, cwd, timeout_s, dirty_problems, "proxy-injected"
                )
            )

            removed = _sanitize_proxy_env()
            stages.append(
                await _probe_target(
                    api_base, target, prompt, cwd, timeout_s, removed, "proxy-cleared"
                )
            )
    finally:
        for key, value in snapshot.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    dirty, clean = stages
    clean_ok = bool(clean.get("ok"))
    return CheckResult(
        name="proxy-vs-agent-chain",
        ok=clean_ok,
        details={
            "runtime_id": target.runtime_id,
            "model_id": target.model_id,
            "injected_proxy": dirty_proxy,
            "dirty_failure_kind": dirty.get("failure_kind")
            or ("ok" if dirty.get("ok") else "unknown"),
            "clean_ok": clean_ok,
            "verdict": _proxy_verdict(dirty, clean_ok),
            "stages": stages,
        },
    )


async def _run_checks(args: argparse.Namespace) -> list[CheckResult]:
    """按命令行选择执行验收项。"""
    detected = _detect_proxy_problems()
    removed_proxies = [] if args.keep_proxy else _sanitize_proxy_env()
    targets = [
        RuntimeTarget("opencode", args.opencode_model),
    ]
    selected = set(
        args.case or ["compression", "rollback", "preview", "search", "context", "proxy"]
    )
    if detected and args.keep_proxy:
        verdict = "env-misconfigured-kept"
    elif detected:
        verdict = "env-misconfigured-auto-cleared"
    else:
        verdict = "env-clean"
    results: list[CheckResult] = [
        CheckResult(
            name="proxy-env",
            ok=not (detected and args.keep_proxy),
            details={
                "verdict": verdict,
                "detected": detected,
                "removed": removed_proxies,
                "kept": args.keep_proxy,
            },
        )
    ]

    if "compression" in selected:
        results.append(_check_compression())
    if "rollback" in selected:
        results.append(_check_rollback())

    external = selected & {"preview", "search", "context", "proxy"}
    if not external:
        return results

    with _serve() as api_base:
        if "preview" in selected:
            results.append(await _check_preview(api_base, targets, args.timeout))
        if "search" in selected:
            results.append(await _check_search(api_base, targets, args.timeout))
        if "context" in selected:
            results.append(await _check_context_switch(api_base, targets, args.timeout))
        if "proxy" in selected:
            proxy_target = next(
                (row for row in targets if row.runtime_id == args.proxy_runtime),
                targets[-1],
            )
            results.append(await _check_proxy(api_base, proxy_target, args.proxy_timeout))
    return results


def main(argv: list[str] | None = None) -> int:
    """解析参数、运行验收并输出 JSON。"""
    parser = argparse.ArgumentParser(description="叮答 Agent 端到端验收")
    parser.add_argument(
        "--case",
        action="append",
        choices=("compression", "rollback", "preview", "search", "context", "proxy"),
        default=[],
        help="只跑指定检查；默认全部",
    )
    parser.add_argument("--opencode-model", default="openrouter/tencent/hy3")
    parser.add_argument("--timeout", type=float, default=300.0, help="单次 Agent 超时秒数")
    parser.add_argument(
        "--proxy-runtime",
        default="opencode",
        help="proxy 归因检查用哪个 runtime（默认 opencode）",
    )
    parser.add_argument(
        "--proxy-timeout",
        type=float,
        default=120.0,
        help="proxy 归因检查单轮超时秒数",
    )
    parser.add_argument("--keep-proxy", action="store_true", help="保留当前代理环境，不清理畸形 URL")
    args = parser.parse_args(argv)

    results = asyncio.run(_run_checks(args))
    for result in results:
        print(f"[{'PASS' if result.ok else 'FAIL'}] {result.name}")
        print(json.dumps(result.details, ensure_ascii=False, indent=2))
    summary = {
        "ok": all(result.ok for result in results),
        "results": [asdict(result) for result in results],
    }
    print("SUMMARY")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
