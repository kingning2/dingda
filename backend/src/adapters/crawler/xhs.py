"""小红书（xhs_cli）适配器。"""

from __future__ import annotations

from typing import Any

from src.adapters.registry import get_export, is_vendor_installed


def get_xhs_client_class() -> type[Any]:
    return get_export("xhs_cli", "client", "XhsClient")


def is_xhs_available() -> bool:
    return is_vendor_installed("xhs_cli")
