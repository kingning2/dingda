"""Runtime registry / stream 单测。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cli.prompts import compose_agent_prompt
from cli.registry import get_runtime, list_runtime_ids
from cli.stream.parse import parse_lines


def test_list_runtime_ids() -> None:
    ids = list_runtime_ids()
    assert "codex" in ids
    assert "claude" in ids
    assert "opencode" in ids


def test_codex_args_include_exec() -> None:
    spec = get_runtime("codex")
    args = spec.build_args({"cwd": "D:/tmp", "model_id": "gpt-5.5"})
    assert args[0] == "exec"
    assert "--json" in args
    assert "--model" in args


def test_codex_resume_args() -> None:
    spec = get_runtime("codex")
    args = spec.build_args({"session_id": "thread_abc", "model_id": "gpt-5.5"})
    assert args[:2] == ["exec", "resume"]
    assert "thread_abc" in args


def test_compose_prompt_resume_skips_system(monkeypatch) -> None:
    monkeypatch.setattr("cli.prompts._skill_prompt", lambda _workdir=None: "## Skills\n")
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    first = compose_agent_prompt("搜露营椅", platform_hint="xianyu", resume=False)
    assert "用户请求" in first
    assert "搜露营椅" in first
    resumed = compose_agent_prompt("继续", resume=True)
    assert "继续" in resumed
    assert "用户请求" not in resumed
    assert "本轮优先平台" not in resumed


def test_compose_prompt_cold_start_injects_prior_context(monkeypatch) -> None:
    monkeypatch.setattr("cli.prompts._skill_prompt", lambda _workdir=None: "## Skills\n")
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    prior = [
        {"role": "user", "content": "先搜闲鱼键盘"},
        {"role": "assistant", "content": "已找到 3 条候选"},
    ]
    cold = compose_agent_prompt(
        "换个 Agent 继续比价",
        resume=False,
        context_messages=prior,
    )
    assert "先前对话（叮答托管）" in cold
    assert "先搜闲鱼键盘" in cold
    assert "换个 Agent 继续比价" in cold

    resumed = compose_agent_prompt(
        "继续",
        resume=True,
        context_messages=prior,
    )
    assert "先前对话（叮答托管）" not in resumed
    assert "继续" in resumed


def test_opencode_args() -> None:
    spec = get_runtime("opencode")
    args = spec.build_args(
        {
            "cwd": "D:/work",
            "session_id": "ses_1",
            "model_id": "anthropic/claude",
            "reasoning": "high",
        }
    )
    assert args[:5] == ["run", "--format", "json", "--auto", "--thinking"]
    assert "--dir" in args and "D:/work" in args
    assert "-s" in args and "ses_1" in args
    assert "-m" in args and "anthropic/claude" in args
    assert "--variant" in args and "high" in args


def test_parse_codex_text_delta() -> None:
    line = '{"type":"item.completed","item":{"text":"你好"}}'
    events = parse_lines("codex-json", line)
    assert events == [{"type": "textDelta", "text": "你好"}]


def test_parse_opencode_text_and_session_dedupe() -> None:
    line = json.dumps(
        {
            "type": "text",
            "sessionID": "ses_test",
            "part": {"type": "text", "text": "hello"},
        },
        ensure_ascii=False,
    )
    state: dict = {}
    events = parse_lines("opencode-json", line, state=state)
    assert events[0] == {"type": "session", "sessionId": "ses_test"}
    assert events[1] == {"type": "textDelta", "text": "hello"}
    again = parse_lines("opencode-json", line, state=state)
    assert again == []


def test_parse_opencode_reasoning_snapshot_to_delta() -> None:
    """reasoning.part.text 是变长快照，第二次只下发增量。"""
    state: dict = {}
    first = json.dumps(
        {"type": "reasoning", "part": {"id": "r1", "text": "Hello"}},
        ensure_ascii=False,
    )
    second = json.dumps(
        {"type": "reasoning", "part": {"id": "r1", "text": "Hello world"}},
        ensure_ascii=False,
    )
    e1 = parse_lines("opencode-json", first, state=state)
    assert e1 == [{"type": "thinking", "text": "Hello"}]
    e2 = parse_lines("opencode-json", second, state=state)
    assert e2 == [{"type": "thinking", "text": " world"}]


def test_parse_opencode_tool_use() -> None:
    line = json.dumps(
        {
            "type": "tool_use",
            "part": {
                "callID": "call_1",
                "tool": "bash",
                "state": {
                    "status": "completed",
                    "input": {"command": "ls"},
                    "output": "ok",
                },
            },
        }
    )
    events = parse_lines("opencode-json", line)
    assert events[0]["type"] == "toolCall"
    assert events[0]["id"] == "call_1"
    assert events[0]["name"] == "bash"
    assert "step" in events[0]
    assert events[1]["type"] == "toolResult"
    assert events[1]["output"] == "ok"


def test_parse_opencode_tool_error_emits_result() -> None:
    """参数写错等 MCP 失败：state.error + status=error，必须结束步骤。"""
    line = json.dumps(
        {
            "type": "tool_use",
            "part": {
                "callID": "call_err",
                "tool": "dingda_search",
                "state": {
                    "status": "error",
                    "input": {"patform": "xianyu", "query": "车配件"},
                    "error": "platform is required",
                },
            },
        }
    )
    events = parse_lines("opencode-json", line)
    assert events[0]["type"] == "toolCall"
    assert events[1]["type"] == "toolResult"
    assert events[1]["step"]["status"]["state"] == "error"
    # 浏览器类工具一开始就挂 PageCard，出错也不额外摘掉
    assert events[0]["step"]["kind"] == "browser_crawl"
    assert events[0]["step"]["page"]["loading"] is True



def test_resolve_binary_prefers_managed(tmp_path: Path, monkeypatch) -> None:
    from cli.registry import resolve_binary

    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.delenv("DINGDA_OPENCODE_PATH", raising=False)
    monkeypatch.setattr(
        "cli.registry.shutil.which",
        lambda *_a, **_k: None,
    )

    spec = get_runtime("opencode")
    managed = home / ".dingda" / "v2" / "runtimes" / "opencode"
    managed.mkdir(parents=True)
    binary = managed / ("opencode.exe" if os.name == "nt" else "opencode")
    binary.write_bytes(b"x")
    assert resolve_binary(spec) == binary


def test_resolve_binary_finds_opencode_home_bin(tmp_path: Path, monkeypatch) -> None:
    from cli.registry import resolve_binary

    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.delenv("DINGDA_OPENCODE_PATH", raising=False)
    monkeypatch.setattr(
        "cli.registry.shutil.which",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "cli.registry._windows_registry_path",
        lambda: "",
    )

    spec = get_runtime("opencode")
    install = home / ".opencode" / "bin"
    install.mkdir(parents=True)
    binary = install / ("opencode.exe" if os.name == "nt" else "opencode")
    binary.write_bytes(b"x")
    assert resolve_binary(spec) == binary


def test_resolve_binary_preferred_strips_extended_prefix(tmp_path: Path) -> None:
    from cli.registry import resolve_binary

    binary = tmp_path / ("opencode.exe" if os.name == "nt" else "opencode")
    binary.write_bytes(b"x")
    preferred = f"\\\\?\\{binary}" if os.name == "nt" else str(binary)
    spec = get_runtime("opencode")
    assert resolve_binary(spec, preferred=preferred) == binary
