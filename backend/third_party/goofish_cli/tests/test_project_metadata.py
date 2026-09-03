"""Project metadata regression checks."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_mcp_dependency_stays_on_fastmcp_compatible_major_version():
    project_root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((project_root / "pyproject.toml").read_text())

    assert "mcp>=1.2,<2" in metadata["project"]["dependencies"]
