"""Agent Skill 渲染 / 安装测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.skill import (
    compose_skills_prompt,
    install,
    render_skills,
)

_SKILLS_DIR = Path(__file__).resolve().parents[2] / "src" / "cli" / "skills"
_SERVER_DIR = Path(__file__).resolve().parents[2]
_UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def test_render_skills_includes_multi_round_compare(tmp_path: Path) -> None:
    rendered = render_skills(tmp_path, "python")
    assert set(rendered) == {
        "dingda-crawl",
        "dingda-source-evidence",
        "dingda-price-compare",
        "dingda-offer-verification",
    }
    crawl = rendered["dingda-crawl"]
    assert "## Resource map" in crawl
    assert "## Workflow" in crawl
    assert "## Output contract" in crawl
    assert "search --platform xianyu" in crawl
    assert "compare --image" in crawl
    assert "references/examples.md" in crawl
    assert str(tmp_path) in crawl
    assert "{{ENTRY}}" not in crawl
    compare = rendered["dingda-price-compare"]
    assert "至少执行 **3 轮成功返回**" in compare
    assert "--rounds 1" in compare
    assert "{{ENTRY}}" not in compare
    assert "{{PYTHON}}" not in compare
    assert str(tmp_path) in compare


def test_install_copies_skill_metadata(tmp_path: Path) -> None:
    install(Path("D:/dingda-server"), "python", home=tmp_path)
    root = tmp_path / ".codex" / "skills"
    assert (root / "dingda-crawl" / "SKILL.md").is_file()
    assert (root / "dingda-crawl" / "agents" / "openai.yaml").is_file()
    cli_reference = root / "dingda-crawl" / "references" / "cli-reference.md"
    assert cli_reference.is_file()
    reference_text = cli_reference.read_text(encoding="utf-8")
    assert "{{ENTRY}}" not in reference_text
    assert "run_tool.py" in reference_text
    runner = root / "dingda-crawl" / "scripts" / "run_tool.py"
    assert runner.is_file()
    assert "{{SERVER_DIR}}" not in runner.read_text(encoding="utf-8")
    examples = root / "dingda-crawl" / "references" / "examples.md"
    assert examples.is_file()
    assert "爬取闲鱼搜索" in examples.read_text(encoding="utf-8")
    assert not (root / "dingda-crawl" / "scripts" / "examples").exists()
    assert (root / "dingda-price-compare" / "SKILL.md").is_file()
    assert (root / "dingda-price-compare" / "agents" / "openai.yaml").is_file()
    assert (root / "dingda-offer-verification" / "SKILL.md").is_file()


def test_compose_skills_prompt_stages_cwd_alias(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    prompt = compose_skills_prompt(Path("D:/dingda-server"), "python", cwd=tmp_path)
    staged = tmp_path / ".dingda-skills" / "dingda-price-compare"
    assert (staged / "SKILL.md").is_file()
    assert (staged / "agents" / "openai.yaml").is_file()
    assert (staged / "scripts" / "validate_rounds.py").is_file()
    assert (staged / "assets" / "round-record.json").is_file()
    assert (staged / "references" / "multiround-policy.md").is_file()
    assert "`.dingda-skills/dingda-price-compare/`" in prompt
    assert "至少执行 **3 轮成功返回**" in prompt


def test_compose_skills_prompt_runs_headroom(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "1")

    def fake_compress(messages, model="x"):
        out = MagicMock()
        out.tokens_saved = 1
        out.tokens_before = 10
        out.tokens_after = 9
        out.messages = [{"role": "system", "content": "COMPRESSED_SKILLS"}]
        return out

    import sys

    sys.modules["headroom"] = MagicMock(compress=fake_compress)
    prompt = compose_skills_prompt(Path("D:/dingda-server"), "python", cwd=tmp_path)
    assert prompt == "COMPRESSED_SKILLS"


def _run_script(relative_path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    script = _SKILLS_DIR / relative_path
    proc = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=_UTF8_ENV,
        check=False,
    )
    if not proc.stdout.strip():
        raise AssertionError(f"{script} produced no stdout: code={proc.returncode} stderr={proc.stderr}")
    return proc.returncode, json.loads(proc.stdout)


def test_source_normalizer_script() -> None:
    code, result = _run_script(
        "dingda-source-evidence/scripts/normalize_source.py",
        {
            "item_id": "xy-1",
            "platform": "xianyu",
            "title": "折叠露营椅",
            "image_url": "https://img.example/source.jpg",
            "price": "89",
            "hard_constraints": ["折叠露营椅", "承重120kg"],
        },
    )
    assert code == 0
    assert result["ok"] is True
    assert result["source_card"]["platform"] == "xianyu"


def test_round_validator_rejects_two_rounds() -> None:
    code, result = _run_script(
        "dingda-price-compare/scripts/validate_rounds.py",
        {
            "rounds": [
                {"round": 1, "strategy": "image", "candidate_ids": ["a"]},
                {
                    "round": 2,
                    "strategy": "attribute-text",
                    "query": "露营椅",
                    "candidate_ids": ["b"],
                },
            ]
        },
    )
    assert code == 2
    assert result["ok"] is False
    assert "at least 3 completed rounds are required" in result["errors"]


def test_offer_scorer_script() -> None:
    code, result = _run_script(
        "dingda-offer-verification/scripts/score_offers.py",
        {
            "offers": [
                {
                    "title": "折叠露营椅",
                    "price": 50,
                    "quantity_included": 1,
                    "price_basis": "piece",
                    "merchant_rating": 4.8,
                },
                {
                    "title": "不同规格椅子",
                    "price": 20,
                    "hard_constraint_mismatches": ["承重规格不符"],
                },
            ]
        },
    )
    assert code == 0
    assert result["ok"] is True
    assert result["counts"]["accept"] == 1
    assert result["counts"]["reject"] == 1


def test_crawl_runner_delegates_to_tool_cli(tmp_path: Path) -> None:
    install(_SERVER_DIR, "python", home=tmp_path)
    runner = tmp_path / ".codex" / "skills" / "dingda-crawl" / "scripts" / "run_tool.py"
    proc = subprocess.run(
        [sys.executable, str(runner), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_UTF8_ENV,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "SyntaxWarning" not in proc.stderr
    assert "search" in proc.stdout
    assert "compare" in proc.stdout


def test_install_replaces_stale_skill_files(tmp_path: Path) -> None:
    target = tmp_path / ".codex" / "skills" / "dingda-crawl"
    stale = target / "scripts" / "examples" / "stale.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    install(_SERVER_DIR, "python", home=tmp_path)

    assert not stale.exists()
    assert (target / "references" / "examples.md").is_file()
