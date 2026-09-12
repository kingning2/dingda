"""Score 1688 candidates against a normalized source card.

Usage:
    python score_offers.py --input verification-input.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    match = _NUMBER.search(str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _known(value: Any) -> bool:
    return value not in (None, "", "unknown", [], {})


def score_offers(raw: dict[str, Any]) -> dict[str, Any]:
    """Return normalized unit prices and accept/conditional/reject verdicts."""
    offers = raw.get("offers")
    if not isinstance(offers, list):
        offers = []

    scored: list[dict[str, Any]] = []
    for index, row in enumerate(offers, start=1):
        if not isinstance(row, dict):
            continue
        candidate = dict(row)
        mismatches = candidate.get("hard_constraint_mismatches")
        mismatches = mismatches if isinstance(mismatches, list) else []
        title = _text(candidate.get("title"))
        price = _number(candidate.get("price") or candidate.get("unit_price"))
        shipping = _number(candidate.get("shipping_cost")) or 0.0
        quantity = _number(candidate.get("quantity_included")) or 1.0
        unit_price = None if price is None else round((price + shipping) / quantity, 2)

        merchant_known = any(
            _known(candidate.get(key))
            for key in ("merchant_rating", "repurchase_rate", "sold_count")
        )
        price_basis_known = _known(candidate.get("price_basis"))

        if not title or mismatches:
            verdict = "reject"
        elif price is None or not price_basis_known:
            verdict = "conditional"
        elif not merchant_known:
            verdict = "conditional"
        else:
            verdict = "accept"

        candidate.update(
            {
                "candidate_index": index,
                "unit_price": unit_price,
                "verdict": verdict,
                "hard_constraint_mismatches": mismatches,
                "merchant_evidence_known": merchant_known,
                "price_basis_known": price_basis_known,
            }
        )
        scored.append(candidate)

    rank = {"accept": 0, "conditional": 1, "reject": 2}
    scored.sort(
        key=lambda item: (
            rank.get(str(item.get("verdict")), 9),
            item.get("unit_price") if item.get("unit_price") is not None else float("inf"),
        )
    )
    survivors = [item for item in scored if item.get("verdict") != "reject"]
    return {
        "ok": bool(survivors),
        "counts": {
            "accept": sum(1 for item in scored if item.get("verdict") == "accept"),
            "conditional": sum(1 for item in scored if item.get("verdict") == "conditional"),
            "reject": sum(1 for item in scored if item.get("verdict") == "reject"),
        },
        "survivors": survivors,
        "offers": scored,
        "message": (
            f"{len(survivors)} candidates survived verification"
            if survivors
            else "no candidate survived verification"
        ),
    }


def _read_json(path: str | None) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score 1688 offers for a source product.")
    parser.add_argument("--input", help="verification input JSON path; defaults to stdin")
    parser.add_argument("--output", help="optional output path; defaults to stdout")
    args = parser.parse_args(argv)

    try:
        result = score_offers(_read_json(args.input))
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "message": str(exc), "offers": []}

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
