"""由 app 生成并安装 agent skill（不走 MCP 的取证路径）。

职责：
    按当前解释器 / 仓库路径 / registry 里实际启用的工具，渲染一份 ``SKILL.md``，
    装到各 CLI runtime 的 skills 目录（codex / opencode / claude）。

设计说明：
    - 手写绝对路径会随环境失效 —— 这里全部按运行时算出来
    - 工具清单取自 ``list_tools()``（跳过 ``internal_only``），加工具自动进文档
    - 只写文件、不删目录：同名 skill 覆盖更新

使用示例：
    python -m src.tools.skill            # 打印渲染结果
    python -m src.tools.skill --install  # 装到各 runtime 的 skills 目录
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL_NAME = "dingda-crawl"

# 各 runtime 读 skill 的目录（相对用户主目录）
_RUNTIME_SKILL_DIRS = (
    Path(".codex") / "skills",
    Path(".config") / "opencode" / "skills",
    Path(".claude") / "skills",
)

_DESCRIPTION = (
    "需要从闲鱼/小红书/1688 实地取证时用——找货、看行情、比价、看内容风向、看某个页面。"
    "会真开浏览器爬，闲鱼/小红书逐条拉详情。"
)

_PLAYBOOK = """\
## 硬要求

1. **闲鱼证据优先**：闲鱼是货盘真相，小红书只是内容风向
2. **闲鱼至少约 100 条样本**、换词跑 ≥3 轮再下结论
3. **不要只看列表**：结论必须基于详情字段（desc / want_count / 卖家）
4. 小红书 1～3 轮够；**视频笔记会跳过**（note_type=video），别当已读
5. 标题偶尔会串成「满足条件时，买家可退货且运费由卖家承担」这类保障文案 ——
   遇到就结合 url / 卖家判断，别把它当商品名

## 执行提示（重要）

这些命令会**真开浏览器爬**，单次 1～3 分钟，比默认 shell 超时长得多。
调 shell 时务必把超时设大（**300000 ms / 5 分钟**以上），否则会被判超时，
看起来像「命令跑不了」，其实只是没等够。
"""


def _entry(server_dir: Path, python: str) -> str:
    return f'"{python}" -m src.tools.cli'


def render_skill(server_dir: Path, python: str) -> str:
    """按当前环境渲染 SKILL.md 全文。"""
    from src.tools.registry import list_tools

    entry = _entry(server_dir, python)
    names = [spec.name for spec in list_tools() if not spec.internal_only]
    lines = [
        "---",
        f"name: {SKILL_NAME}",
        f"description: {_DESCRIPTION}",
        "---",
        "",
        "# 叮答爬虫（命令行版）",
        "",
        "要用**真实数据**支撑结论时跑下面这些命令。**不要凭记忆编造商品**；爬不到就如实说爬不到。",
        "",
        f"工作目录必须是 `{server_dir}`；解释器用绝对路径（下面命令里已带）。",
        "",
        "## 可用工具",
        "",
    ]
    for spec in list_tools():
        if spec.internal_only:
            continue
        flags = " ".join(
            f"--{name.replace('_', '-')}"
            + ("" if field.is_required() else "?")
            for name, field in spec.input_model.model_fields.items()
        )
        lines.append(f"- `{spec.name}` — {spec.description.strip()[:100]}")
        lines.append(f"  ```bash")
        lines.append(f"  {entry} {spec.name} {flags}".rstrip())
        lines.append(f"  ```")
    lines += [
        "",
        "参数都是 `--连字符` 形式（`--item-id`，不是 `--item_id`）；带 `?` 的可选。",
        f"看全部子命令与参数说明：`{entry} --help`。",
        "",
        "## 输出与排错",
        "",
        "- stdout 是**纯 JSON**（日志在 stderr）：`ok=true` 看 `items`；`ok=false` 看 `error_code`",
        "- `error_code=account.session_expired` → 让用户去界面扫码，别硬编",
        "",
        _PLAYBOOK,
    ]
    assert names, "registry 里没有可用工具"
    return "\n".join(lines)


def install(server_dir: Path, python: str, *, home: Path | None = None) -> list[Path]:
    """渲染并写入各 runtime 的 skills 目录；返回写出的路径。"""
    text = render_skill(server_dir, python)
    root = home or Path.home()
    written: list[Path] = []
    for rel in _RUNTIME_SKILL_DIRS:
        target = root / rel / SKILL_NAME / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
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
    print(render_skill(server_dir, python))
    return 0


if __name__ == "__main__":
    sys.exit(main())
