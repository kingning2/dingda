#!/usr/bin/env python3
"""Sync contracts to codegen output directories (grouped by domain, incremental).

产物按 schema 顶层目录聚合为一个域一个文件：agent / ai / channel / plugin / runtime。
Rust 输出到 ``src/contracts/gen``（模块 ``crate::contracts::gen``），
由手写 ``src/contracts/mod.rs`` 统一 ``pub use`` 重导出。
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from _common import CONTRACTS, ROOT, delete_if_exists, setup_logging, write_text_if_changed

TS_OUT = ROOT / "packages" / "contracts" / "src" / "generated"
PY_OUT = ROOT / "python" / "src" / "dingda_sidecar" / "contracts"
RS_OUT = ROOT / "apps" / "desktop" / "src-tauri" / "src" / "contracts" / "gen"

TYPE_MAP_TS = {
    "string": "string",
    "boolean": "boolean",
    "integer": "number",
    "number": "number",
}
TYPE_MAP_RS = {
    "string": "String",
    "boolean": "bool",
    "integer": "i64",
    "number": "f64",
}
TYPE_MAP_PY = {
    "string": "str",
    "boolean": "bool",
    "integer": "int",
    "number": "float",
}


@dataclass
class SyncStats:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0

    @property
    def changed(self) -> int:
        return self.added + self.updated + self.deleted


@dataclass
class SchemaEntry:
    pascal: str
    snake: str
    group: str
    schema: dict
    rel: Path

    @property
    def is_enum(self) -> bool:
        return "enum" in self.schema and "properties" not in self.schema


def _schema_names(rel: Path) -> tuple[str, str]:
    parts = list(rel.parts[:-1])
    stem = rel.name.removesuffix(".schema.json")
    if "." in stem:
        name_part, direction = stem.rsplit(".", 1)
        parts.extend([name_part, direction])
    else:
        parts.append(stem)
    pascal = "".join(
        "".join(seg[:1].upper() + seg[1:] for seg in part.split("_") if seg) for part in parts
    )
    snake = "_".join(parts)
    return pascal, snake


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_ref(ref: str, current_rel: Path, schema_root: Path) -> tuple[str, str]:
    if ref.startswith("#/"):
        raise ValueError(f"JSON-pointer refs not supported: {ref}")
    current_dir = (schema_root / current_rel).parent
    target = (current_dir / ref).resolve()
    try:
        rel = target.relative_to(schema_root.resolve())
    except ValueError as error:
        raise ValueError(f"ref outside schema root: {ref}") from error
    return _schema_names(rel)


def _collect_refs(
    spec: dict,
    current_rel: Path,
    schema_root: Path,
) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    if "$ref" in spec:
        refs.append(_resolve_ref(spec["$ref"], current_rel, schema_root))
    if spec.get("type") == "array":
        refs.extend(_collect_refs(spec.get("items", {}), current_rel, schema_root))
    return refs


def _prop_type_ts(spec: dict, current_rel: Path, schema_root: Path) -> str:
    if "$ref" in spec:
        return _resolve_ref(spec["$ref"], current_rel, schema_root)[0]
    stype = spec.get("type", "string")
    if stype == "array":
        items = spec.get("items", {})
        return f"{_prop_type_ts(items, current_rel, schema_root)}[]"
    return TYPE_MAP_TS.get(stype, "unknown")


def _prop_type_rs(spec: dict, current_rel: Path, schema_root: Path) -> str:
    if "$ref" in spec:
        return _resolve_ref(spec["$ref"], current_rel, schema_root)[0]
    stype = spec.get("type", "string")
    if stype == "array":
        items = spec.get("items", {})
        return f"Vec<{_prop_type_rs(items, current_rel, schema_root)}>"
    return TYPE_MAP_RS.get(stype, "String")


def _prop_type_py(spec: dict, current_rel: Path, schema_root: Path) -> str:
    if "$ref" in spec:
        return _resolve_ref(spec["$ref"], current_rel, schema_root)[0]
    stype = spec.get("type", "string")
    if stype == "array":
        items = spec.get("items", {})
        return f"list[{_prop_type_py(items, current_rel, schema_root)}]"
    return TYPE_MAP_PY.get(stype, "str")


def _schema_refs(schema: dict, rel: Path, schema_root: Path) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for spec in schema.get("properties", {}).values():
        refs.extend(_collect_refs(spec, rel, schema_root))
    return sorted(set(refs))


def _enum_values(schema: dict) -> list[str]:
    return [str(value) for value in schema["enum"]]


def _enum_variant(value: str) -> str:
    return "".join(seg[:1].upper() + seg[1:] for seg in value.split("_") if seg)


def _cross_group_refs(
    entry: SchemaEntry,
    group_of: dict[str, str],
    schema_root: Path,
) -> dict[str, list[str]]:
    """按目标域归组的跨域引用：{group: [PascalName, ...]}。"""
    by_group: dict[str, list[str]] = {}
    if entry.is_enum:
        return by_group
    for pascal, snake in _schema_refs(entry.schema, entry.rel, schema_root):
        target_group = group_of[snake]
        if target_group == entry.group:
            continue
        names = by_group.setdefault(target_group, [])
        if pascal not in names:
            names.append(pascal)
    return by_group


def _emit_ts_group(entries: list[SchemaEntry], group_of: dict[str, str], schema_root: Path) -> str:
    lines = ["// Auto-generated by sync_contracts.py — do not edit.", ""]
    imports: dict[str, set[str]] = {}
    for entry in entries:
        for target_group, names in _cross_group_refs(entry, group_of, schema_root).items():
            imports.setdefault(target_group, set()).update(names)
    for target_group in sorted(imports):
        names = ", ".join(sorted(imports[target_group]))
        lines.append(f'import type {{ {names} }} from "./{target_group}";')
    if len(lines) > 2:
        lines.append("")

    for entry in entries:
        if entry.is_enum:
            values = " | ".join(f'"{value}"' for value in _enum_values(entry.schema))
            lines.append(f"export type {entry.pascal} = {values};")
            lines.append("")
            continue
        schema = entry.schema
        required = set(schema.get("required", []))
        lines.append(f"export interface {entry.pascal} {{")
        for prop, spec in schema.get("properties", {}).items():
            ts_type = _prop_type_ts(spec, entry.rel, schema_root)
            optional = "" if prop in required else "?"
            lines.append(f"  {prop}{optional}: {ts_type};")
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_RUST_KEYWORDS = {
    "as",
    "async",
    "await",
    "box",
    "break",
    "const",
    "continue",
    "crate",
    "do",
    "dyn",
    "else",
    "enum",
    "extern",
    "false",
    "final",
    "fn",
    "for",
    "if",
    "impl",
    "in",
    "let",
    "loop",
    "macro",
    "match",
    "mod",
    "move",
    "mut",
    "override",
    "priv",
    "pub",
    "ref",
    "return",
    "self",
    "static",
    "struct",
    "super",
    "trait",
    "true",
    "try",
    "type",
    "typeof",
    "unsafe",
    "unsized",
    "use",
    "virtual",
    "where",
    "while",
    "yield",
}


def _rs_field_name(prop: str) -> str:
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", prop).lower()
    # serde 对 `r#type` 字段仍按 JSON key "type" 匹配。
    if name in _RUST_KEYWORDS:
        return f"r#{name}"
    return name


def _emit_rs_group(entries: list[SchemaEntry], group_of: dict[str, str], schema_root: Path) -> str:
    lines = ["// Auto-generated by sync_contracts.py — do not edit.", ""]
    imports: dict[str, set[str]] = {}
    for entry in entries:
        for target_group, names in _cross_group_refs(entry, group_of, schema_root).items():
            imports.setdefault(target_group, set()).update(names)
    for target_group in sorted(imports):
        names = sorted(imports[target_group])
        if len(names) == 1:
            lines.append(f"use super::{target_group}::{names[0]};")
        else:
            lines.append(f"use super::{target_group}::{{{', '.join(names)}}};")
    if imports:
        lines.append("")
    lines.append("use serde::{Deserialize, Serialize};")
    lines.append("")

    for entry in entries:
        if entry.is_enum:
            lines.append("#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]")
            lines.append('#[serde(rename_all = "snake_case")]')
            lines.append(f"pub enum {entry.pascal} {{")
            for value in _enum_values(entry.schema):
                lines.append(f"    {_enum_variant(value)},")
            lines.append("}")
            lines.append("")
            continue
        schema = entry.schema
        required = set(schema.get("required", []))
        lines.append("#[derive(Debug, Clone, Serialize, Deserialize)]")
        lines.append(f"pub struct {entry.pascal} {{")
        for prop, spec in schema.get("properties", {}).items():
            rs_type = _prop_type_rs(spec, entry.rel, schema_root)
            if prop not in required:
                rs_type = f"Option<{rs_type}>"
            field = _rs_field_name(prop)
            if field != prop:
                lines.append(f'    #[serde(rename = "{prop}")]')
            lines.append(f"    pub {field}: {rs_type},")
        lines.append("}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _emit_py_group(entries: list[SchemaEntry], group_of: dict[str, str], schema_root: Path) -> str:
    needs_typed_dict = any(not e.is_enum for e in entries)
    needs_literal = any(e.is_enum for e in entries)
    imports: dict[str, set[str]] = {}
    for entry in entries:
        for target_group, names in _cross_group_refs(entry, group_of, schema_root).items():
            imports.setdefault(target_group, set()).update(names)

    lines = ['"""Auto-generated from contracts/schema."""', ""]
    # 延迟求值注解：同组类型可前向引用，定义顺序无关。
    lines.append("from __future__ import annotations")
    lines.append("")
    typing_names = sorted(
        name
        for wanted, name in ((needs_typed_dict, "TypedDict"), (needs_literal, "Literal"))
        if wanted
    )
    if typing_names:
        lines.append(f"from typing import {', '.join(typing_names)}")
    if imports:
        lines.append("")
    for target_group in sorted(imports):
        names = ", ".join(sorted(imports[target_group]))
        lines.append(f"from .{target_group} import {names}")
    lines.append("")
    lines.append("")

    for entry in entries:
        if entry.is_enum:
            lines.append(f"{entry.pascal} = Literal[")
            lines.extend(f'    "{value}",' for value in _enum_values(entry.schema))
            lines.append("]")
            lines.append("")
            lines.append("")
            continue
        schema = entry.schema
        required = set(schema.get("required", []))
        props = schema.get("properties", {})
        if required == set(props):
            lines.append(f"class {entry.pascal}(TypedDict):")
        else:
            lines.append(f"class {entry.pascal}(TypedDict, total=False):")
        if not props:
            lines.append("    pass")
        else:
            for prop, spec in props.items():
                py_type = _prop_type_py(spec, entry.rel, schema_root)
                lines.append(f"    {prop}: {py_type}")
        lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _track_write(
    path: Path,
    content: str,
    *,
    dry_run: bool,
    stats: SyncStats,
    quiet: bool,
) -> None:
    existed = path.exists()
    if write_text_if_changed(path, content, dry_run=dry_run):
        action = "updated" if existed else "added"
        if action == "updated":
            stats.updated += 1
        else:
            stats.added += 1
        if not quiet:
            logging.info("%s %s", action, path.relative_to(ROOT))
    else:
        stats.unchanged += 1


def _cleanup_stale(
    out_dir: Path,
    expected_stems: set[str],
    extension: str,
    *,
    skip: set[str],
    dry_run: bool,
    stats: SyncStats,
    quiet: bool,
) -> None:
    if not out_dir.exists():
        return
    for path in sorted(out_dir.glob(f"*{extension}")):
        if path.name in skip or path.stem in expected_stems:
            continue
        if delete_if_exists(path, dry_run=dry_run):
            stats.deleted += 1
            if not quiet:
                logging.info("deleted %s", path.relative_to(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show actions only")
    parser.add_argument("--quiet", action="store_true", help="only log summary")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)
    quiet = args.quiet and not args.verbose

    schema_root = CONTRACTS / "schema" / "v1"
    if not schema_root.exists():
        logging.warning("no schemas at %s", schema_root)
        return 0

    entries: list[SchemaEntry] = []
    for path in sorted(schema_root.rglob("*.schema.json")):
        rel = path.relative_to(schema_root)
        pascal, snake = _schema_names(rel)
        entries.append(
            SchemaEntry(
                pascal=pascal,
                snake=snake,
                group=rel.parts[0],
                schema=_load_schema(path),
                rel=rel,
            )
        )
    if not entries:
        logging.warning("no schemas at %s", schema_root)
        return 0

    group_of = {entry.snake: entry.group for entry in entries}
    groups = sorted({entry.group for entry in entries})
    stats = SyncStats()
    expected_stems = set(groups)

    for group in groups:
        group_entries = sorted((e for e in entries if e.group == group), key=lambda e: e.snake)
        _track_write(
            TS_OUT / f"{group}.ts",
            _emit_ts_group(group_entries, group_of, schema_root),
            dry_run=args.dry_run,
            stats=stats,
            quiet=quiet,
        )
        _track_write(
            PY_OUT / f"{group}.py",
            _emit_py_group(group_entries, group_of, schema_root),
            dry_run=args.dry_run,
            stats=stats,
            quiet=quiet,
        )
        _track_write(
            RS_OUT / f"{group}.rs",
            _emit_rs_group(group_entries, group_of, schema_root),
            dry_run=args.dry_run,
            stats=stats,
            quiet=quiet,
        )

    _cleanup_stale(
        TS_OUT,
        expected_stems,
        ".ts",
        skip={"index.ts"},
        dry_run=args.dry_run,
        stats=stats,
        quiet=quiet,
    )
    _cleanup_stale(
        PY_OUT,
        expected_stems,
        ".py",
        skip={"__init__.py"},
        dry_run=args.dry_run,
        stats=stats,
        quiet=quiet,
    )
    _cleanup_stale(
        RS_OUT,
        expected_stems,
        ".rs",
        skip={"mod.rs"},
        dry_run=args.dry_run,
        stats=stats,
        quiet=quiet,
    )

    ts_index = (
        "// Auto-generated by sync_contracts.py — do not edit.\n\n"
        + "\n".join(f'export * from "./{group}";' for group in groups)
        + "\n"
    )
    py_lines = ['"""Auto-generated contract index."""', ""]
    all_names: list[str] = []
    for group in groups:
        names = sorted(e.pascal for e in entries if e.group == group)
        all_names.extend(names)
        py_lines.append(f"from .{group} import (")
        py_lines.extend(f"    {name}," for name in names)
        py_lines.append(")")
    py_lines.append("")
    py_lines.append("__all__ = [")
    py_lines.extend(f'    "{name}",' for name in sorted(all_names))
    py_lines.append("]")
    py_index = "\n".join(py_lines) + "\n"
    rs_index = (
        "// Auto-generated by sync_contracts.py — do not edit.\n\n"
        + "\n".join(f"pub mod {group};" for group in groups)
        + "\n"
    )

    _track_write(TS_OUT / "index.ts", ts_index, dry_run=args.dry_run, stats=stats, quiet=quiet)
    _track_write(PY_OUT / "__init__.py", py_index, dry_run=args.dry_run, stats=stats, quiet=quiet)
    _track_write(RS_OUT / "mod.rs", rs_index, dry_run=args.dry_run, stats=stats, quiet=quiet)

    if stats.changed == 0:
        logging.info("contracts unchanged (%d schemas, %d groups)", len(entries), len(groups))
    else:
        logging.info(
            "contracts synced (%d schemas, %d groups): +%d ~%d -%d (%d unchanged)",
            len(entries),
            len(groups),
            stats.added,
            stats.updated,
            stats.deleted,
            stats.unchanged,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
