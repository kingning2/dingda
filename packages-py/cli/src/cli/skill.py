"""由 app 生成并安装 agent skill（工具面唯一的取证路径）。

职责：
    按当前解释器 / registry 里实际启用的工具渲染 Skills，
    注入 prompt 并复制到工作目录；同时装到各 CLI runtime 的 skills 目录作 fallback。

设计说明：
    - 工具包已装进 venv：``tool`` 裸入口在任意目录可跑，模板不再需要 server 目录或解释器路径
    - 四个业务 Skill 全部从静态模板渲染，工具清单由模板显式维护
    - 比价拆成来源证据 / 多轮编排 / 候选验收三个独立 Skill
    - 每次安装替换同名 Skill 目录，旧资源不会残留
    - 落盘 SKILL.md 保持原文；``compose_skills_prompt`` 注入时经 Headroom 压缩

使用示例：
    python -m cli.skill              # 打印全部 Skill
    python -m cli.skill --install    # 装到各 runtime 的 skills 目录
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("dingda.cli.skill")

@dataclass(frozen=True)
class SkillSpec:
    """一个 Skill 的静态登记项：名字 + 一句话职责。"""

    name: str
    summary: str


# Skill 总表（map）：名字 → 登记项。渲染 / 安装都从这里取，
# 角色只声明「我要哪几个」（下面的数组），不各抄一份清单。
SKILLS: dict[str, SkillSpec] = {
    "dingda-crawl": SkillSpec(
        "dingda-crawl", "命令行取证手册：search / product / compare / login / preview"
    ),
    "dingda-source-evidence": SkillSpec(
        "dingda-source-evidence", "锁定比价来源：商品、硬约束与价格口径"
    ),
    "dingda-price-compare": SkillSpec(
        "dingda-price-compare", "多轮比价：换策略搜 1688 候选，每轮回传同一 source"
    ),
    "dingda-offer-verification": SkillSpec(
        "dingda-offer-verification", "候选验收：同款程度 / 到手价 / 商家证据 / 供货风险"
    ),
    "dingda-orchestrate": SkillSpec(
        "dingda-orchestrate", "编排：child_run / child_status / child_resume / repair_dom"
    ),
}

# 角色按用途取数组（顺序 = 注入顺序）
WORKER_SKILL_NAMES: tuple[str, ...] = (
    "dingda-crawl",
    "dingda-source-evidence",
    "dingda-price-compare",
    "dingda-offer-verification",
)
ORCHESTRATE_SKILL_NAMES: tuple[str, ...] = ("dingda-orchestrate",)
SKILL_NAMES: tuple[str, ...] = WORKER_SKILL_NAMES + ORCHESTRATE_SKILL_NAMES

_SKILL_TEMPLATE_DIR = Path(__file__).resolve().parents[0] / "skills"
SKILLS_CWD_ALIAS = ".dingda-skills"
_SAFE_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TEXT_SUFFIXES = frozenset({".json", ".md", ".py", ".txt", ".yaml", ".yml"})

# Skill 命令里的工具入口：装进 venv 的裸 console script（见 tools/pyproject.toml）。
# 写死名字而不是解释器路径 —— 既不让模型看见开发机的仓库位置，也省得命令随解释器搬家失效。
SKILL_TOOL_ENTRY = "tool"

# 各 runtime 读 skill 的目录（相对用户主目录）
_RUNTIME_SKILL_DIRS = (
    Path(".codex") / "skills",
    Path(".config") / "opencode" / "skills",
    Path(".claude") / "skills",
)


def _render_text(text: str, python: str) -> str:
    """替换 Skill 模板中的运行时占位符。"""
    return text.replace("{{ENTRY}}", SKILL_TOOL_ENTRY).replace("{{PYTHON}}", python)


def _render_template_skill(name: str, python: str) -> str:
    """读取静态 Skill 模板并替换运行时占位符。"""
    path = _SKILL_TEMPLATE_DIR / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    return _render_text(text, python).strip() + "\n"


def _render_resource(source: Path, python: str) -> bytes:
    """按文件类型渲染 Skill 资源；二进制资源原样保留。"""
    if source.suffix.lower() not in _TEXT_SUFFIXES:
        return source.read_bytes()
    text = source.read_text(encoding="utf-8")
    return _render_text(text, python).encode("utf-8")


def _render_skill_resources(
    name: str,
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
        resources.append((source.relative_to(source_dir), _render_resource(source, python)))
    return resources


def _replace_skill_dir(target: Path) -> None:
    """替换受管 Skill 目录，确保安装结果与模板完全一致。"""
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)


def render_skills(python: str) -> dict[str, str]:
    """按当前环境渲染全部 Skill；返回 name -> SKILL.md。"""
    return {name: _render_template_skill(name, python) for name in SKILL_NAMES}


def stage_skills(
    cwd: Path,
    python: str,
    *,
    names: tuple[str, ...] = SKILL_NAMES,
) -> list[Path]:
    """把 Skill 复制到 cwd 的相对别名目录，返回 staged 目录列表。"""
    rendered = render_skills(python)
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

        for relative, content in _render_skill_resources(name, python):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        staged.append(target)
    return staged


def compose_skills_prompt(
    python: str,
    *,
    cwd: Path | None = None,
    names: tuple[str, ...] = SKILL_NAMES,
) -> str:
    """把全部 Skill 正文和资源根路径拼成宿主注入块。"""
    rendered = render_skills(python)
    staged_names: set[str] = set()
    if cwd is not None:
        try:
            staged_names = {path.name for path in stage_skills(cwd, python, names=names)}
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
        lines.append(f'<skill name="{name}">')
        # 只暴露「工作目录相对路径」或用户主目录的安装位，**绝不**写仓库模板的
        # 绝对路径 —— 那是开发机上的 packages-py/cli/src/cli/skills，Agent 顺着它
        # 一路 ls 上去就翻到仓库源码，思考过程里会混进实现细节（也会把叮答的
        # skill 与用户自己的 skill / 工程文件搅在一起）。
        if name in staged_names:
            lines.append(f"工作目录相对路径：`{SKILLS_CWD_ALIAS}/{name}/`（优先用这个）")
        else:
            lines.append(f"已安装路径（若本机有）：`{Path.home() / '.codex' / 'skills' / name}`")
        lines += ["", body.strip(), "", "</skill>", ""]
    from core.compress import compress_text

    return compress_text("\n".join(lines).strip() + "\n")


def install(python: str, *, home: Path | None = None) -> list[Path]:
    """渲染并写入各 runtime 的 Skills 目录；返回写出的路径。"""
    rendered = render_skills(python)
    root = home or Path.home()
    written: list[Path] = []
    for name, text in rendered.items():
        resources = _render_skill_resources(name, python)
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
    args = parser.parse_args(argv)

    python = args.python.strip() or str(Path(sys.executable).resolve())
    if args.install:
        for path in install(python):
            print(f"installed -> {path}".encode("ascii", "backslashreplace").decode())
        return 0
    rendered = render_skills(python)
    print("\n\n---\n\n".join(rendered.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
