"""Branch role resolution and active Cursor rule generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "tooling" / "dingda" / "config" / "branch_roles.json"
ACTIVE_RULE_PATH = ROOT / ".cursor" / "rules" / "active-branch.mdc"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class RoleConfig:
    key: str
    label: str
    description: str
    branch_prefix: str
    allowed_globs: tuple[str, ...]
    optional_globs: tuple[str, ...]
    forbidden_globs: tuple[str, ...]
    rule_files: tuple[str, ...]


@dataclass(frozen=True)
class KindConfig:
    key: str
    label: str
    description: str


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def list_role_keys() -> list[str]:
    config = load_config()
    return [key for key in config["roles"] if key != "integration"]


def list_kind_keys() -> list[str]:
    config = load_config()
    return list(config["branch_kinds"].keys())


def role_from_config(key: str) -> RoleConfig:
    config = load_config()
    if key not in config["roles"]:
        raise KeyError(f"unknown role: {key}")
    raw = config["roles"][key]
    return RoleConfig(
        key=key,
        label=raw["label"],
        description=raw["description"],
        branch_prefix=raw["branch_prefix"],
        allowed_globs=tuple(raw["allowed_globs"]),
        optional_globs=tuple(raw.get("optional_globs", [])),
        forbidden_globs=tuple(raw.get("forbidden_globs", [])),
        rule_files=tuple(raw.get("rule_files", [])),
    )


def kind_from_config(key: str) -> KindConfig:
    config = load_config()
    kinds = config.get("branch_kinds", {})
    if key not in kinds:
        raise KeyError(f"unknown branch kind: {key}")
    raw = kinds[key]
    return KindConfig(key=key, label=raw["label"], description=raw["description"])


def validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not slug:
        raise ValueError("slug is required (e.g. m5-ui-shell)")
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(f"invalid slug: {slug!r} (use kebab-case, e.g. m5-ui-shell)")
    return slug


def validate_kind(kind: str) -> str:
    kind = kind.strip().lower()
    if not kind:
        raise ValueError(
            "branch kind is required (feature | fix | hotfix | chore | refactor | docs)"
        )
    if not KIND_RE.fullmatch(kind):
        raise ValueError(f"invalid kind: {kind!r}")
    if kind not in list_kind_keys():
        choices = ", ".join(list_kind_keys())
        raise ValueError(f"unknown kind {kind!r}; choose: {choices}")
    return kind


def branch_name_for(role_key: str, kind: str, slug: str) -> str:
    role = role_from_config(role_key)
    kind_key = validate_kind(kind)
    slug_key = validate_slug(slug)
    return f"{role.branch_prefix}/{kind_key}/{slug_key}"


def parse_branch(branch: str) -> tuple[str | None, str | None, str | None]:
    """Return (role_key, kind, slug) when parseable."""
    config = load_config()
    roles = set(config["roles"]) - {"integration"}
    kinds = set(config.get("branch_kinds", {}))

    if branch.startswith("role/"):
        suffix = branch.removeprefix("role/")
        if suffix in roles:
            return suffix, None, None

    parts = branch.split("/")
    if len(parts) == 3 and parts[0] in roles and parts[1] in kinds:
        return parts[0], parts[1], parts[2]

    if len(parts) == 2 and parts[0] in roles:
        return parts[0], None, parts[1]

    return None, None, None


def resolve_role(branch: str) -> RoleConfig:
    config = load_config()
    legacy = config.get("legacy_branch_map", {})
    if branch in legacy:
        return role_from_config(legacy[branch])
    if branch == "main":
        return role_from_config("integration")

    role_key, _, _ = parse_branch(branch)
    if role_key:
        return role_from_config(role_key)

    raise ValueError(
        f"cannot infer role from branch {branch!r}; "
        f"use <role>/<kind>/<slug> (e.g. frontend/feature/m5-ui-shell) or main"
    )


def render_active_rule(branch: str, role: RoleConfig) -> str:
    _, kind, slug = parse_branch(branch)
    kind_line = ""
    if kind:
        try:
            kind_cfg = kind_from_config(kind)
            kind_line = f"\n**类型：** {kind_cfg.label} (`{kind}`) — {kind_cfg.description}\n"
        except KeyError:
            kind_line = f"\n**类型：** `{kind}`\n"
    if slug:
        kind_line += f"\n**任务：** `{slug}`\n"

    allowed = "\n".join(f"- `{g}`" for g in role.allowed_globs)
    optional = (
        "\n".join(f"- `{g}`" for g in role.optional_globs)
        if role.optional_globs
        else "- _(无 — 非本分支职责)_"
    )
    forbidden = (
        "\n".join(f"- `{g}`" for g in role.forbidden_globs)
        if role.forbidden_globs
        else "- _(无额外禁止路径)_"
    )
    rules = (
        "\n".join(f"- [`.cursor/rules/{name}`]({name})" for name in role.rule_files)
        if role.rule_files
        else "- [`master.md`](master.md) only"
    )

    return f"""---
description: Active branch scope for {branch} (auto-generated — run pnpm branch:sync)
alwaysApply: true
---

# 当前分支：`{branch}`

**角色：** {role.label}
{kind_line}
{role.description}

## 允许修改

{allowed}

## 可选（跨端契约 — 先改 Contract 再 codegen）

{optional}

## 禁止修改（除非用户明确要求扩 scope）

{forbidden}

## 细则规则

{rules}

---

> 由 `tooling/dingda/scripts/sync_branch_rules.py` 根据分支名生成。
> 切换分支后若约束不符，运行 `pnpm branch:sync`。
"""


def sync_active_rule(*, branch: str | None = None, dry_run: bool = False) -> Path:
    if branch is None:
        import subprocess

        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        if not branch:
            raise RuntimeError("detached HEAD — checkout a branch first")

    role = resolve_role(branch)
    content = render_active_rule(branch, role)
    if dry_run:
        return ACTIVE_RULE_PATH

    ACTIVE_RULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_RULE_PATH.write_text(content, encoding="utf-8", newline="\n")
    return ACTIVE_RULE_PATH
