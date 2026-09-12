"""preview / live_hub 单测。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cli.live import hub as live_hub
from tools.preview import PreviewInput
from tools.registry import get_tool, list_tools


def test_preview_registered() -> None:
    names = {spec.name for spec in list_tools()}
    assert "preview" in names
    spec = get_tool("preview")
    assert spec.input_model is PreviewInput


def test_preview_input_requires_http() -> None:
    with pytest.raises(ValidationError):
        PreviewInput(url="ftp://example.com")
    with pytest.raises(ValidationError):
        PreviewInput(url="not-a-url")
    ok = PreviewInput(url="https://example.com/path")
    assert ok.url.startswith("https://")


def test_live_hub_queue() -> None:
    live_hub.open_run("run-test")
    live_hub.push_frame("run-test", {"type": "browserFrame", "url": "https://a"})
    live_hub.push_frame("run-test", {"type": "browserFrame", "url": "https://b"})
    drained = live_hub.drain("run-test")
    assert len(drained) == 2
    assert live_hub.drain("run-test") == []
    live_hub.close_run("run-test")
