"""文档加载 — 从路径读取文本。

``load_text`` / ``load_texts`` 为切分与建索引提供原始字符串输入。"""

from __future__ import annotations

from pathlib import Path


def load_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def load_texts(paths: list[str | Path]) -> list[str]:
    return [load_text(path) for path in paths]
