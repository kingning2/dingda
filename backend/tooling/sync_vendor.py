"""从上游仓库同步 third_party vendor 包（整仓拷贝，版本锁定）。

用法（在 backend 目录下）：
    uv run python tooling/sync_vendor.py xhs_cli          # 按 vendor.lock.yaml 同步
    uv run python tooling/sync_vendor.py --all
    uv run python tooling/sync_vendor.py --update xhs_cli  # 拉 upstream.ref 最新并更新锁
    uv run python tooling/sync_vendor.py --update --all

同步后会自动：
    - 检出锁定 rev（commit / tag）到 third_party/<path>/（排除 .git）
    - 删除 manifest 中的 CLI/MCP 入口（路径相对 vendor 根）
    - 更新 third_party/vendor.lock.yaml（仅 --update 时改写 rev）

业务代码无需修改；适配入口见 src/adapters/。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY = BACKEND_ROOT / "third_party"
MANIFEST = THIRD_PARTY / "manifest.yaml"
LOCKFILE = THIRD_PARTY / "vendor.lock.yaml"


def load_manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}


def load_lock() -> dict:
    if not LOCKFILE.exists():
        return {}
    return yaml.safe_load(LOCKFILE.read_text(encoding="utf-8")) or {}


def save_lock(data: dict) -> None:
    header = (
        "# 第三方 vendor 版本锁（由 tooling/sync_vendor.py 维护）\n"
        "# 日常 sync 使用 rev；升级上游请加 --update\n\n"
    )
    LOCKFILE.write_text(
        header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _ignore_git(_dir: str, names: list[str]) -> list[str]:
    return [name for name in names if name == ".git"]


def _resolve_remote_ref(repo: str, ref: str) -> str:
    """把分支名解析为完整 commit SHA。"""
    result = subprocess.run(
        ["git", "ls-remote", repo, ref],
        check=True,
        capture_output=True,
        text=True,
    )
    line = result.stdout.strip().splitlines()
    if not line:
        raise SystemExit(f"无法解析上游引用: {repo} {ref}")
    sha = line[0].split()[0]
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit(f"上游返回无效 SHA: {sha}")
    return sha


def _checkout_vendor(repo: str, rev: str, clone_dir: Path) -> str:
    """克隆并检出 rev，返回实际检出的完整 SHA。"""
    subprocess.run(
        ["git", "clone", "--filter=blob:none", repo, str(clone_dir)],
        check=True,
    )
    subprocess.run(["git", "-C", str(clone_dir), "checkout", "--quiet", rev], check=True)
    result = subprocess.run(
        ["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def sync_one(name: str, *, update_lock: bool) -> None:
    """同步单个 vendor（整仓）。"""
    vendors = load_manifest().get("vendors", {})
    entry = vendors.get(name)
    if not entry:
        raise SystemExit(f"manifest 中未找到 vendor: {name}")

    upstream = entry["upstream"]
    repo = upstream["repo"]
    branch = upstream.get("ref", "main")
    target = THIRD_PARTY / entry["path"]

    lock_data = load_lock()
    lock_vendors = lock_data.setdefault("vendors", {})
    locked = lock_vendors.get(name, {})

    if update_lock:
        rev = _resolve_remote_ref(repo, branch)
        print(f"[sync] {name} <- {repo} (update {branch} -> {rev[:12]})")
    else:
        rev = locked.get("rev")
        locked_repo = locked.get("repo")
        if not rev:
            raise SystemExit(
                f"{name} 未在 vendor.lock.yaml 中锁定，"
                f"请先执行: uv run python tooling/sync_vendor.py --update {name}"
            )
        if locked_repo and locked_repo != repo:
            raise SystemExit(
                f"{name} 锁文件 repo 与 manifest 不一致: {locked_repo} != {repo}"
            )
        print(f"[sync] {name} <- {repo} (locked {rev[:12]})")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        clone_dir = tmp_path / "repo"
        checked_out = _checkout_vendor(repo, rev, clone_dir)

        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(clone_dir, target, ignore=_ignore_git)

    for rel in entry.get("remove_files", []):
        path = target / rel
        if path.is_file():
            print(f"[sync] remove {path.relative_to(BACKEND_ROOT)}")
            path.unlink()

    rewrite = entry.get("rewrite_imports")
    if rewrite:
        _rewrite_imports(target, rewrite["from_prefix"], rewrite["to_prefix"])

    lock_vendors[name] = {"repo": repo, "rev": checked_out}
    save_lock(lock_data)
    print(f"[sync] done -> {target.relative_to(BACKEND_ROOT)} (rev {checked_out[:12]})")


def _rewrite_imports(root: Path, from_prefix: str, to_prefix: str) -> None:
    """批量改写 vendor 内 import 前缀。"""
    if from_prefix == to_prefix:
        return
    pattern_from = re.compile(
        rf"^(\s*(?:from|import)\s+){re.escape(from_prefix)}(\.|[^\s]*)"
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        new_text = pattern_from.sub(rf"\1{to_prefix}\2", text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            print(f"[sync] rewrite imports in {path.name}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="同步 third_party vendor 包（版本锁定）")
    parser.add_argument("names", nargs="*", help="vendor 名称，如 xhs_cli")
    parser.add_argument("--all", action="store_true", help="同步 manifest 中全部 vendor")
    parser.add_argument(
        "--update",
        action="store_true",
        help="拉取 manifest upstream.ref 最新提交并更新 vendor.lock.yaml",
    )
    args = parser.parse_args(argv)

    names = list(args.names)
    if args.all:
        names = list(load_manifest().get("vendors", {}).keys())
    if not names:
        parser.error("请指定 vendor 名称或使用 --all")

    for name in names:
        sync_one(name, update_lock=args.update)


if __name__ == "__main__":
    main()
