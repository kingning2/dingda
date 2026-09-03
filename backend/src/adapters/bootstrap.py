"""第三方路径引导。"""

from __future__ import annotations

import sys
from pathlib import Path

_THIRD_PARTY_ROOT = Path(__file__).resolve().parents[2] / "third_party"


def third_party_root() -> Path:
    return _THIRD_PARTY_ROOT


def ensure_third_party_path() -> Path:
    root = str(_THIRD_PARTY_ROOT.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    return _THIRD_PARTY_ROOT


def bootstrap_third_party() -> None:
    ensure_third_party_path()


def register_adapters() -> None:
    """占位：业务适配器注册在后续迁移阶段实现。"""
