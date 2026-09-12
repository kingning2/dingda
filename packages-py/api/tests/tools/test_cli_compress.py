"""tools.cli 出口走 Headroom 压缩。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field


class _In(BaseModel):
    query: str = Field(description="q")


class _Out(BaseModel):
    ok: bool = True
    blob: str = ""


def test_cli_main_applies_compress_tool_payload(capsys, monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")
    spec = MagicMock()
    spec.name = "search"
    spec.description = "search tools"
    spec.internal_only = False
    spec.input_model = _In

    payload = _Out(ok=True, blob="x" * 5000)
    compressed = {"ok": True, "blob": "zipped"}

    with patch("tools.registry.list_tools", return_value=[spec]):
        with patch("tools.registry.get_tool", return_value=spec):
            with patch(
                "tools.registry.call_tool",
                return_value=payload,
            ):
                with patch(
                    "core.compress.compress_tool_payload",
                    return_value=compressed,
                ) as compress_mock:
                    from tools.cli import main

                    code = main(["search", "--query", "键盘"])
    assert code == 0
    compress_mock.assert_called_once()
    assert compress_mock.call_args.kwargs.get("tool_name") == "search"
    out = json.loads(capsys.readouterr().out.strip())
    assert out == compressed
