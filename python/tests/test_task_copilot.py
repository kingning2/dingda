"""任务副驾 — LangGraph 编译与 AG-UI 事件流。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from dingda_sidecar.agent.workflows.task_copilot import (
    COPILOT_GRAPH_STEPS,
    CopilotRun,
    _compile_copilot_graph,
    _execute,
    _extract_text_parts,
    register_run,
)


class TestCopilotGraphCompile(unittest.TestCase):
    def test_compile_has_react_nodes(self) -> None:
        model = MagicMock()
        model.bind_tools.return_value = model
        compiled = _compile_copilot_graph(model, [])
        nodes = set(compiled.get_graph().nodes)
        self.assertEqual(COPILOT_GRAPH_STEPS, ("prepare", "agent", "tools"))
        for name in COPILOT_GRAPH_STEPS:
            self.assertIn(name, nodes)


class TestExtractTextParts(unittest.TestCase):
    def test_splits_reasoning_from_additional_kwargs(self) -> None:
        from langchain_core.messages import AIMessageChunk

        chunk = AIMessageChunk(
            content="答案",
            additional_kwargs={"reasoning_content": "思考"},
        )
        reasoning, content = _extract_text_parts(chunk)
        self.assertEqual(reasoning, "思考")
        self.assertEqual(content, "答案")


class TestTaskCopilotExecute(unittest.TestCase):
    def test_execute_streams_via_compiled_graph(self) -> None:
        run = CopilotRun(
            run_id="test-run",
            thread_id="thread-1",
            settings_api_key="",
            settings_base_url="https://api.example.com/v1",
            settings_model="gpt-4o-mini",
        )
        events: list[dict] = []
        run.sink = events.append
        register_run(run)

        mock_graph = MagicMock()
        mock_graph.stream.return_value = iter([])

        with (
            patch(
                "dingda_sidecar.agent.graph.model.create_chat_model",
                return_value=MagicMock(),
            ),
            patch(
                "dingda_sidecar.agent.workflows.task_copilot._compile_copilot_graph",
                return_value=mock_graph,
            ) as compile_graph,
            patch("dingda_sidecar.agent.workflows.task_copilot._build_tools", return_value=[]),
        ):
            _execute(run)

        compile_graph.assert_called_once()
        mock_graph.stream.assert_called_once()
        stream_args, stream_kwargs = mock_graph.stream.call_args
        self.assertEqual(stream_kwargs.get("stream_mode"), "messages")
        initial = stream_args[0]
        self.assertFalse(initial.get("context_injected"))
        self.assertEqual(initial.get("task_context"), {})

        types = [event.get("type") for event in events]
        self.assertIn("RUN_STARTED", types)
        self.assertIn("RUN_FINISHED", types)
        self.assertNotIn("RUN_ERROR", types)

        started = next(event for event in events if event.get("type") == "RUN_STARTED")
        self.assertEqual(started.get("thread_id"), "thread-1")
        self.assertEqual(started.get("run_id"), "test-run")


if __name__ == "__main__":
    unittest.main()
