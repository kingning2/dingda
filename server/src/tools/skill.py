"""由 app 生成并安装 agent skill（不走 MCP 的取证路径）。

职责：
    按当前解释器 / 仓库路径 / registry 里实际启用的工具渲染 Skills，
    注入 prompt 并复制到工作目录；同时装到各 CLI runtime 的 skills 目录作 fallback。

设计说明：
    - 手写绝对路径会随环境失效 —— 这里全部按运行时算出来
    - 四个业务 Skill 全部从静态模板渲染，工具清单由模板显式维护
    - 比价拆成来源证据 / 多轮编排 / 候选验收三个独立 Skill
    - 每次安装替换同名 Skill 目录，旧资源不会残留
    - 落盘 SKILL.md 保持原文；``compose_skills_prompt`` 注入时经 Headroom 压缩

使用示例：
    python -m src.tools.skill              # 打印全部 Skill
    python -m src.tools.skill --install    # 装到各 runtime 的 skills 目录
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from pathlib import Path

logger = logging.getLogger("dingda.tools.skill")

SKILL_NAME = "dingda-crawl"
SKILL_NAMES = (
    SKILL_NAME,
    "dingda-source-evidence",
    "dingda-price-compare",
    "dingda-offer-verification",
)
_SKILL_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "cli" / "skills"
SKILLS_CWD_ALIAS = ".dingda-skills"
_SAFE_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TEXT_SUFFIXES = frozenset({".json", ".md", ".py", ".txt", ".yaml", ".yml"})

# 各 runtime 读 skill 的目录（相对用户主目录）
_RUNTIME_SKILL_DIRS = (
    Path(".codex") / "skills",
    Path(".config") / "opencode" / "skills",
    Path(".claude") / "skills",
)

def _entry(server_dir: Path, python: str) -> str:
    return f'"{python}" -m src.tools.cli'


def _render_text(text: str, server_dir: Path, python: str) -> str:
    """替换 Skill 模板中的运行时路径。"""
    return (
        text.replace("{{ENTRY}}", _entry(server_dir, python))
        .replace("{{PYTHON}}", python)
        .replace("{{SERVER_DIR}}", str(server_dir))
    )


def _render_template_skill(name: str, server_dir: Path, python: str) -> str:
    """读取静态 Skill 模板并替换运行时路径。"""
    path = _SKILL_TEMPLATE_DIR / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    return _render_text(text, server_dir, python).strip() + "\n"


def _render_resource(source: Path, server_dir: Path, python: str) -> bytes:
    """按文件类型渲染 Skill 资源；二进制资源原样保留。"""
    if source.suffix.lower() not in _TEXT_SUFFIXES:
        return source.read_bytes()
    text = source.read_text(encoding="utf-8")
    return _render_text(text, server_dir, python).encode("utf-8")


def _render_skill_resources(
    name: str,
    server_dir: Path,
    python: str,
) -> list[tuple[Path, bytes]]:
    """渲染一个 Skill 除 SKILL.md 外的全部资源，返回相对路径与内容。"""
    source_dir = _SKILL_TEMPLATE_DIR / name
    resources: list[tuple[Path, bytes]] = []
    if not source_dir.is_dir():
        return resources
    for source in source_dir.rglob("*"):
        if not source.is_file() or source.name == "SKILL.md":
            continue
        resources.append(
            (
                source.relative_to(source_dir),
                _render_resource(source, server_dir, python),
            )
        )
    return resources


def _replace_skill_dir(target: Path) -> None:
    """替换受管 Skill 目录，确保安装结果与模板完全一致。"""
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)


def render_skills(server_dir: Path, python: str) -> dict[str, str]:
    """按当前环境渲染全部 Skill；返回 name -> SKILL.md。"""
    return {
        name: _render_template_skill(name, server_dir, python)
        for name in SKILL_NAMES
    }


def stage_skills(
    cwd: Path,
    server_dir: Path,
    python: str,
    *,
    names: tuple[str, ...] = SKILL_NAMES,
) -> list[Path]:
    """把 Skill 复制到 cwd 的相对别名目录，返回 staged 目录列表。"""
    rendered = render_skills(server_dir, python)
    alias_root = Path(cwd).resolve() / SKILLS_CWD_ALIAS
    if alias_root.is_symlink():
        alias_root.unlink()
    elif alias_root.exists() and not alias_root.is_dir():
        raise OSError(f"{alias_root} is not a directory")
    alias_root.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []

    for name in names:
        if name not in rendered or not _SAFE_SKILL_NAME.fullmatch(name):
            logger.warning("skip unsafe skill name=%s", name)
            continue
        target = alias_root / name
        _replace_skill_dir(target)
        (target / "SKILL.md").write_text(rendered[name], encoding="utf-8")

        for relative, content in _render_skill_resources(name, server_dir, python):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        staged.append(target)
    return staged


def compose_skills_prompt(
    server_dir: Path,
    python: str,
    *,
    cwd: Path | None = None,
    names: tuple[str, ...] = SKILL_NAMES,
) -> str:
    """把全部 Skill 正文和资源根路径拼成宿主注入块。"""
    rendered = render_skills(server_dir, python)
    staged_names: set[str] = set()
    if cwd is not None:
        try:
            staged_names = {path.name for path in stage_skills(
                cwd,
                server_dir,
                python,
                names=names,
            )}
        except (OSError, shutil.Error):
            logger.exception("stage skills failed cwd=%s", cwd)

    lines = [
        "## Required Agent Skills",
        "",
        "以下 Skill 由叮答宿主直接注入。必须按依赖顺序执行，不能只依赖运行时自动发现。",
        "",
    ]
    for name in names:
        body = rendered.get(name)
        if not body:
            continue
        source_dir = (_SKILL_TEMPLATE_DIR / name).resolve()
        lines.append(f'<skill name="{name}">')
        lines.append(f"绝对路径 fallback：`{source_dir}`")
        if name in staged_names:
            lines.append(f"工作目录相对路径：`{SKILLS_CWD_ALIAS}/{name}/`")
        lines += ["", body.strip(), "", "</skill>", ""]
    from src.agent.core.compress import compress_text

    return compress_text("\n".join(lines).strip() + "\n")


def install(server_dir: Path, python: str, *, home: Path | None = None) -> list[Path]:
    """渲染并写入各 runtime 的 Skills 目录；返回写出的路径。"""
    rendered = render_skills(server_dir, python)
    root = home or Path.home()
    written: list[Path] = []
    for name, text in rendered.items():
        resources = _render_skill_resources(name, server_dir, python)
        for rel in _RUNTIME_SKILL_DIRS:
            target_dir = root / rel / name
            _replace_skill_dir(target_dir)
            target = target_dir / "SKILL.md"
            target.write_text(text, encoding="utf-8")
            written.append(target)
            for relative, content in resources:
                target = target_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                written.append(target)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 / 安装叮答 agent skill")
    parser.add_argument("--install", action="store_true", help="写到各 runtime 的 skills 目录")
    parser.add_argument("--python", default="", help="解释器路径（默认当前解释器）")
    parser.add_argument("--server-dir", default="", help="仓库 server 目录（默认按本文件推）")
    args = parser.parse_args(argv)

    server_dir = Path(args.server_dir).resolve() if args.server_dir else Path(__file__).resolve().parents[2]
    python = args.python.strip() or str(Path(sys.executable).resolve())
    if args.install:
        for path in install(server_dir, python):
            print(f"installed -> {path}".encode("ascii", "backslashreplace").decode())
        return 0
    rendered = render_skills(server_dir, python)
    print("\n\n---\n\n".join(rendered.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
