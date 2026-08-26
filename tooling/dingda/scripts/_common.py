"""Shared utilities for DingDa skill scripts."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CRATES = ROOT / "crates"
CONTRACTS = ROOT / "contracts"
DESKTOP_FEATURES = ROOT / "apps" / "desktop" / "src" / "features"
SRC_TAURI = ROOT / "apps" / "desktop" / "src-tauri" / "src"
PYTHON_PACKAGES = ROOT / "python" / "packages"
PYTHON_SIDECAR = ROOT / "python" / "sidecar"
CARGO_TOML = ROOT / "Cargo.toml"
PYPROJECT_TOML = ROOT / "pyproject.toml"

FORBIDDEN_SUFFIXES = ("Manager", "Service", "System", "Engine", "Processor", "Helper", "Util")
FEATURES = frozenset(
    {
        "chat",
        "agent",
        "workflow",
        "knowledge",
        "browser",
        "ocr",
        "mcp",
        "plugin",
        "tenant",
        "user",
        "channel",
    }
)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
        stream=sys.stdout,
    )


def validate_name(name: str) -> str:
    name = name.strip().lower().replace("-", "_")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError(f"invalid name: {name!r} (use lowercase snake_case)")
    for suffix in FORBIDDEN_SUFFIXES:
        if name.endswith(suffix.lower()):
            raise ValueError(f"name must not end with forbidden suffix: {suffix}")
    return name


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str, *, dry_run: bool = False) -> None:
    if dry_run:
        logging.info("[dry-run] would write %s", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    logging.info("wrote %s", path)


def write_text_if_changed(path: Path, content: str, *, dry_run: bool = False) -> bool:
    """Write file only when content differs. Returns True if written."""
    if dry_run:
        if path.exists() and read_text(path) == content:
            logging.debug("[dry-run] unchanged %s", path)
            return False
        logging.info("[dry-run] would write %s", path)
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and read_text(path) == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def delete_if_exists(path: Path, *, dry_run: bool = False) -> bool:
    """Delete file when present. Returns True if deleted."""
    if not path.exists():
        return False
    if dry_run:
        logging.info("[dry-run] would delete %s", path)
        return True
    path.unlink()
    return True


def ensure_workspace_member(crate_name: str, *, dry_run: bool = False) -> None:
    content = read_text(CARGO_TOML)
    entry = f'  "crates/{crate_name}",'
    if entry in content:
        logging.debug("workspace already contains %s", crate_name)
        return
    marker = '[workspace]\nresolver = "2"\nmembers = [\n'
    if marker not in content:
        raise RuntimeError("could not parse root Cargo.toml workspace.members")
    content = content.replace(marker, marker + entry + "\n")
    write_text(CARGO_TOML, content, dry_run=dry_run)


def _insert_sorted_toml_list_entry(
    content: str,
    section_header: str,
    list_name: str,
    entry: str,
) -> str:
    """Insert a quoted list entry under a TOML section, keeping entries sorted."""
    pattern = (
        rf"(\[{re.escape(section_header)}\]\n{re.escape(list_name)} = \[\n)"
        rf"(.*?)"
        rf"(\n\])"
    )
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        raise RuntimeError(f"could not parse [{section_header}] {list_name}")

    lines = [line for line in match.group(2).split("\n") if line.strip()]
    if entry in lines:
        return content

    lines.append(entry)
    lines.sort(key=lambda line: line.strip().strip('",'))
    new_block = "\n".join(lines)
    return content[: match.start(2)] + new_block + content[match.end(2) :]


def ensure_uv_workspace_member(member_path: str, *, dry_run: bool = False) -> None:
    """Register a path in root pyproject.toml [tool.uv.workspace].members."""
    if not PYPROJECT_TOML.exists():
        raise RuntimeError(f"missing root pyproject.toml: {PYPROJECT_TOML}")

    entry = f'  "{member_path}",'
    content = read_text(PYPROJECT_TOML)
    if entry in content:
        logging.debug("uv workspace already contains %s", member_path)
        return

    updated = _insert_sorted_toml_list_entry(
        content,
        "tool.uv.workspace",
        "members",
        entry,
    )
    write_text(PYPROJECT_TOML, updated, dry_run=dry_run)


def ensure_ruff_first_party(package_name: str, *, dry_run: bool = False) -> None:
    """Register import name in [tool.ruff.lint.isort] known-first-party."""
    if not PYPROJECT_TOML.exists():
        raise RuntimeError(f"missing root pyproject.toml: {PYPROJECT_TOML}")

    entry = f'  "{package_name}",'
    content = read_text(PYPROJECT_TOML)
    if entry in content:
        logging.debug("ruff known-first-party already contains %s", package_name)
        return

    updated = _insert_sorted_toml_list_entry(
        content,
        "tool.ruff.lint.isort",
        "known-first-party",
        entry,
    )
    write_text(PYPROJECT_TOML, updated, dry_run=dry_run)


def ensure_pub_mod(mod_file: Path, mod_name: str, *, dry_run: bool = False) -> None:
    """Append `pub mod <name>;` to a Rust mod.rs if missing."""
    content = read_text(mod_file) if mod_file.exists() else ""
    line = f"pub mod {mod_name};"
    if line in content:
        return
    if content and not content.endswith("\n"):
        content += "\n"
    content += f"\n{line}\n"
    write_text(mod_file, content, dry_run=dry_run)


def ensure_python_import(init_file: Path, import_line: str, *, dry_run: bool = False) -> None:
    """Append an import line to Python __init__.py if missing."""
    content = read_text(init_file) if init_file.exists() else ""
    if import_line in content:
        return
    if content and not content.endswith("\n"):
        content += "\n"
    content += f"\n{import_line}\n"
    write_text(init_file, content, dry_run=dry_run)
