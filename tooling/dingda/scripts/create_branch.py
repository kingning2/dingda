#!/usr/bin/env python3
"""Create a role-scoped git branch and sync Cursor rules."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "dingda" / "scripts"))

from _common import setup_logging  # noqa: E402
from branch_roles import (  # noqa: E402
    branch_name_for,
    kind_from_config,
    list_kind_keys,
    list_role_keys,
    role_from_config,
    sync_active_rule,
    validate_kind,
    validate_slug,
)


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, check=check)


def _run_capture(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def _current_branch() -> str:
    result = _run_capture(["git", "branch", "--show-current"])
    return (result.stdout or "").strip()


def _branch_exists(name: str) -> bool:
    result = _run_capture(["git", "rev-parse", "--verify", name], check=False)
    return result.returncode == 0


def _resolve_base(base: str) -> str:
    _run(["git", "fetch", "origin", base], check=False)
    if _branch_exists(base):
        return base
    remote = f"origin/{base}"
    if _branch_exists(remote):
        return remote
    raise RuntimeError(f"base branch not found: {base} (tried {base!r} and {remote!r})")


def _prompt_role() -> str:
    keys = list_role_keys()
    print("\nDingDa — 创建分支\n")
    print("命名规范: <role>/<kind>/<slug>\n")
    for index, key in enumerate(keys, start=1):
        role = role_from_config(key)
        print(f"  {index}) {key:<10} — {role.label}")
    print()
    while True:
        choice = input("选择角色 (编号或名称): ").strip().lower()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(keys):
                return keys[idx]
        if choice in keys:
            return choice
        print("无效选择，请重试。")


def _prompt_kind() -> str:
    keys = list_kind_keys()
    print("\n分支类型 (kind):\n")
    for index, key in enumerate(keys, start=1):
        kind = kind_from_config(key)
        print(f"  {index}) {key:<10} — {kind.label}")
    print()
    while True:
        choice = input("选择类型 (编号或名称): ").strip().lower()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(keys):
                return keys[idx]
        try:
            return validate_kind(choice)
        except ValueError as exc:
            print(exc)


def _prompt_slug() -> str:
    while True:
        slug = input("任务 slug (kebab-case，如 m5-ui-shell): ").strip()
        try:
            return validate_slug(slug)
        except ValueError as exc:
            print(exc)


def _prompt_base(default: str = "main") -> str:
    base = input(f"基于分支 [{default}]: ").strip() or default
    _resolve_base(base)
    return base


def create_branch(
    role_key: str,
    kind: str,
    slug: str,
    *,
    base: str = "main",
    checkout: bool = True,
) -> str:
    name = branch_name_for(role_key, kind, slug)
    if _branch_exists(name):
        raise RuntimeError(f"branch already exists: {name}")

    start_point = _resolve_base(base)
    _run(["git", "branch", name, start_point])
    if checkout:
        _run(["git", "checkout", name])
        sync_active_rule(branch=name)
    return name


def main() -> int:
    kinds = ", ".join(list_kind_keys())
    parser = argparse.ArgumentParser(
        description="Create branch: <role>/<kind>/<slug>",
        epilog=(
            "Examples:\n"
            "  python create_branch.py frontend feature m5-ui-shell\n"
            "  python create_branch.py python fix sidecar-logging\n"
            "  python create_branch.py contract chore agent-v2-schema\n"
            f"\nKinds: {kinds}\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("role", nargs="?", help="frontend | python | contract")
    parser.add_argument("kind", nargs="?", help=f"branch kind: {kinds}")
    parser.add_argument("slug", nargs="?", help="kebab-case slug, e.g. m5-ui-shell")
    parser.add_argument("-i", "--interactive", action="store_true", help="prompt for inputs")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument("--no-checkout", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        if args.interactive or not args.role:
            role_key = _prompt_role()
            kind = _prompt_kind()
            slug = _prompt_slug()
            base = _prompt_base(args.base)
        else:
            role_key = args.role.strip().lower()
            if role_key not in list_role_keys():
                choices = ", ".join(list_role_keys())
                raise ValueError(f"unknown role {role_key!r}; choose: {choices}")
            if not args.kind or not args.slug:
                raise ValueError("usage: create_branch.py <role> <kind> <slug>")
            kind = validate_kind(args.kind.strip().lower())
            slug = validate_slug(args.slug.strip())
            base = args.base

        name = create_branch(
            role_key,
            kind,
            slug,
            base=base,
            checkout=not args.no_checkout,
        )
        role = role_from_config(role_key)
        kind_cfg = kind_from_config(kind)
        print(f"\nOK Created branch `{name}`")
        print(f"   role: {role.label}")
        print(f"   kind: {kind_cfg.label} ({kind})")
        if not args.no_checkout:
            print("OK Synced rules -> .cursor/rules/active-branch.mdc")
            print(f"OK Current branch: {_current_branch()}")
        return 0
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
