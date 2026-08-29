"""GraphContext.llm 走 stream 并回调累计正文。"""

from __future__ import annotations

import unittest

from dingda_sidecar.agent.graph.config import GraphConfig
from dingda_sidecar.agent.graph.context import GraphContext, _delta_text


class _Chunk:
    def __init__(self, content: object) -> None:
        self.content = content


class _FakeModel:
    def stream(self, _messages: object) -> list[_Chunk]:
        return [_Chunk("你"), _Chunk("好"), _Chunk("世界")]

    def invoke(self, _messages: object) -> _Chunk:
        return _Chunk("不应走到 invoke")


class _EmptyStreamModel:
    def stream(self, _messages: object) -> list[_Chunk]:
        return []

    def invoke(self, _messages: object) -> _Chunk:
        return _Chunk("fallback")


class TestGraphLlmStream(unittest.TestCase):
    def test_chunk_text_blocks(self) -> None:
        self.assertEqual(_delta_text(_Chunk("ab")), "ab")
        self.assertEqual(
            _delta_text(_Chunk([{"type": "text", "text": "x"}, {"type": "text", "text": "y"}])),
            "xy",
        )

    def test_llm_streams_and_emits(self) -> None:
        ctx = GraphContext(GraphConfig())
        ctx._model = _FakeModel()  # type: ignore[assignment]
        seen: list[str] = []
        ctx.on_llm = seen.append
        self.assertEqual(ctx.llm("q"), "你好世界")
        self.assertEqual(seen[-1], "你好世界")
        self.assertTrue(any(item == "你" or item.startswith("你") for item in seen))

    def test_llm_empty_stream_falls_back_to_invoke(self) -> None:
        ctx = GraphContext(GraphConfig())
        ctx._model = _EmptyStreamModel()  # type: ignore[assignment]
        seen: list[str] = []
        ctx.on_llm = seen.append
        self.assertEqual(ctx.llm("q"), "fallback")
        self.assertEqual(seen, ["fallback"])

    def test_openai_sse_reasoning_then_content(self) -> None:
        class _Delta:
            def __init__(
                self, content: str | None = None, reasoning_content: str | None = None
            ) -> None:
                self.content = content
                self.reasoning_content = reasoning_content

        class _Sse:
            def __init__(self, reasoning: str | None = None, content: str | None = None) -> None:
                self.choices = [type("C", (), {"delta": _Delta(content, reasoning)})()]

        class _Client:
            def create(self, **kwargs: object) -> list[_Sse]:
                assert kwargs.get("stream") is True
                return [
                    _Sse(reasoning="思"),
                    _Sse(reasoning="考"),
                    _Sse(content="答"),
                    _Sse(content="案"),
                ]

        class _Sdk:
            model_name = "ep-test"
            client = _Client()

            def stream(self, _messages: object) -> list[object]:
                raise AssertionError("应走 client.create")

            def invoke(self, _messages: object) -> object:
                raise AssertionError("不应 invoke")

        ctx = GraphContext(GraphConfig())
        ctx._model = _Sdk()  # type: ignore[assignment]
        seen: list[str] = []
        ctx.on_llm = seen.append
        self.assertEqual(ctx.llm("q"), "思考答案")
        self.assertEqual(seen[-1], "思考答案")
        self.assertGreaterEqual(len(seen), 1)


if __name__ == "__main__":
    unittest.main()
