"""validate_cli：选择器入参解析与失败码（桥的往返见 test_validate.py）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.validate_cli import _load_selectors, main


def test_load_selectors_from_json() -> None:
    assert _load_selectors('{"price":"#p","desc":" "}') == {"price": "#p"}


def test_load_selectors_from_file(tmp_path: Path) -> None:
    path = tmp_path / "selectors.json"
    path.write_text('{"price":"#p"}', encoding="utf-8")
    assert _load_selectors(f"@{path}") == {"price": "#p"}


def test_main_reports_bad_selectors(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--selectors", "not-json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "bad-selectors"


def test_main_reports_missing_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DINGDA_VALIDATE_URL", raising=False)
    assert main(["--selectors", '{"price":"#p"}']) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "validate-url-missing"
