#!/usr/bin/env python3
"""Sync .cursor/rules/active-branch.mdc from current git branch name."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "dingda" / "scripts"))

from _common import setup_logging  # noqa: E402
from branch_roles import sync_active_rule  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", help="override branch name (default: current)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    setup_logging(args.verbose and not args.quiet)

    try:
        path = sync_active_rule(branch=args.branch, dry_run=args.dry_run)
        if not args.quiet:
            import subprocess

            branch = (
                args.branch
                or subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            )
            if args.dry_run:
                print(f"[dry-run] would write {path} for branch {branch}")
            else:
                print(f"synced active-branch rules for `{branch}` → {path.relative_to(ROOT)}")
        return 0
    except (RuntimeError, ValueError) as exc:
        if not args.quiet:
            print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
