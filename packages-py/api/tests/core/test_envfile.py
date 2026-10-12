"""load_dotenv_file：Server 读 .env 的唯一入口，真实环境变量优先。"""

from __future__ import annotations

from pathlib import Path

from core.config import load_dotenv_file


def test_loads_new_keys_and_skips_comments(tmp_path: Path, monkeypatch) -> None:
    """注释 / 空行跳过，KEY=VALUE 注入；锚点目录由参数给定。"""
    (tmp_path / ".env").write_text(
        "# 注释行\n"
        "\n"
        "DINGDA_TEST_PLAIN=hello\n"
        "  DINGDA_TEST_PADDED = spaced \n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DINGDA_TEST_PLAIN", raising=False)
    monkeypatch.delenv("DINGDA_TEST_PADDED", raising=False)

    load_dotenv_file(tmp_path)

    assert "hello" == __import__("os").environ["DINGDA_TEST_PLAIN"]
    assert "spaced" == __import__("os").environ["DINGDA_TEST_PADDED"]


def test_real_env_wins_and_missing_file_is_noop(tmp_path: Path, monkeypatch) -> None:
    """已存在的真实环境变量不被 .env 覆盖；缺文件静默跳过。"""
    (tmp_path / ".env").write_text("DINGDA_TEST_KEEP=file_value\n")
    monkeypatch.setenv("DINGDA_TEST_KEEP", "env_value")

    load_dotenv_file(tmp_path)
    assert "env_value" == __import__("os").environ["DINGDA_TEST_KEEP"]

    load_dotenv_file(tmp_path / "no-such-dir")
    assert "env_value" == __import__("os").environ["DINGDA_TEST_KEEP"]
