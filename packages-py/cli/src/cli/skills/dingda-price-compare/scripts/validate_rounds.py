"""Validate a multi-round 1688 comparison before recommendations are allowed.

Usage:
    python validate_rounds.py --input round-record.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def validate_rounds(raw: dict[str, Any]) -> dict[str, Any]:
    """Check round count, strategy diversity, and unique candidate coverage."""
    errors: list[str] = []
    warnings: list[str] = []
    rounds = raw.get("rounds")
    if not isinstance(rounds, list):
        rounds = []

    strategies: list[str] = []
    queries: list[str] = []
    candidate_ids: set[str] = set()
    for index, row in enumerate(rounds, start=1):
        if not isinstance(row, dict):
            errors.append(f"round {index} must be an object")
            continue
        strategy = _text(row.get("strategy")) or f"round-{index}"
        query = _text(row.get("query"))
        strategies.append(strategy)
        if query:
            queries.append(query)
        ids = row.get("candidate_ids")
        if isinstance(ids, list):
            candidate_ids.update(_text(item) for item in ids if _text(item))

    if len(rounds) < 3:
        errors.append("at least 3 completed rounds are required")
    if "image" not in strategies:
        errors.append("one round must use the source image")
    text_rounds = [strategy for strategy in strategies if strategy != "image"]
    if len(text_rounds) < 2:
        errors.append("at least 2 text rounds with different strategies are required")
    if len(set(queries)) < 2:
        errors.append("text rounds must use at least 2 distinct non-empty queries")
    if len(candidate_ids) < 6:
        warnings.append("fewer than 6 unique candidates; add a targeted round")

    return {
        "ok": not errors,
        "round_count": len(rounds),
        "strategies": strategies,
        "unique_candidate_count": len(candidate_ids),
        "errors": errors,
        "warnings": warnings,
        "summary": (
            f"{len(rounds)} rounds, {len(candidate_ids)} unique candidates"
            if rounds
            else "no rounds recorded"
        ),
    }


def _read_json(path: str | None) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate multi-round compare evidence.")
    parser.add_argument("--input", help="round-record JSON path; defaults to stdin")
    parser.add_argument("--output", help="optional output path; defaults to stdout")
    args = parser.parse_args(argv)

    try:
        result = validate_rounds(_read_json(args.input))
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "errors": [str(exc)], "warnings": []}

    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
        sys.stdout.write(text)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
