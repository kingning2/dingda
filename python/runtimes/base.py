"""子 Runtime 协议 — start / stop / status。"""

from __future__ import annotations

from typing import Any, Protocol

from runtime.context import RuntimeContext


class SubRuntime(Protocol):
    name: str

    def start(self, ctx: RuntimeContext) -> None: ...

    def stop(self) -> None: ...

    def status(self) -> dict[str, Any]: ...
