"""第三方模块注册表。"""

from __future__ import annotations

import importlib
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.adapters.bootstrap import third_party_root
from src.shared.errors import AppError

_MANIFEST = third_party_root() / "manifest.yaml"


class VendorNotInstalledError(AppError):
    def __init__(self, name: str) -> None:
        super().__init__(
            "vendor.not_installed",
            f"第三方工具未安装: {name}（请运行 tooling/sync_vendor.py {name}）",
            status_code=503,
        )


@lru_cache
def load_manifest() -> dict[str, Any]:
    if not _MANIFEST.is_file():
        return {"vendors": {}}
    return yaml.safe_load(_MANIFEST.read_text(encoding="utf-8")) or {}


def vendor_dir(name: str) -> Path:
    vendors = load_manifest().get("vendors", {})
    entry = vendors.get(name)
    if not entry:
        raise AppError("vendor.unknown", f"manifest 中未登记: {name}", status_code=500)
    return third_party_root() / entry["path"]


def is_vendor_installed(name: str) -> bool:
    vendors = load_manifest().get("vendors", {})
    entry = vendors.get(name)
    if not entry:
        return False
    root = vendor_dir(name)
    if not root.is_dir():
        return False
    pkg_root = root / entry.get("python_path", ".")
    package = pkg_root / entry["import_name"]
    return package.is_dir() and any(package.rglob("*.py"))


def ensure_vendor_path(name: str) -> Path:
    vendors = load_manifest().get("vendors", {})
    entry = vendors.get(name)
    if not entry:
        raise AppError("vendor.unknown", f"manifest 中未登记: {name}", status_code=500)
    path = str((vendor_dir(name) / entry.get("python_path", ".")).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)
    return Path(path)


def import_vendor(name: str):
    vendors = load_manifest().get("vendors", {})
    entry = vendors.get(name)
    if not entry:
        raise AppError("vendor.unknown", f"manifest 中未登记: {name}", status_code=500)
    if not is_vendor_installed(name):
        raise VendorNotInstalledError(name)
    ensure_vendor_path(name)
    return importlib.import_module(entry["import_name"])


def get_export(vendor: str, module: str, attr: str) -> Any:
    root = import_vendor(vendor)
    mod = importlib.import_module(f"{root.__name__}.{module}") if module else root
    return getattr(mod, attr)
