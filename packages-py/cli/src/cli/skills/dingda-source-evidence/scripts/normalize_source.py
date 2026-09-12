"""Normalize a raw source product into a source_card JSON object.

Usage:
    python normalize_source.py --input raw-source.json
    python normalize_source.py --input raw-source.json --output source-card.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def normalize_source(raw: dict[str, Any]) -> dict[str, Any]:
    """Build a stable source_card and report missing comparison prerequisites."""
    errors: list[str] = []
    warnings: list[str] = []

    item_id = _text(raw.get("item_id") or raw.get("id"))
    platform = _text(raw.get("platform"))
    url = _text(raw.get("url") or raw.get("product_url"))
    title = _text(raw.get("title"))
    image_url = _text(raw.get("image_url") or raw.get("image"))

    if not platform:
        errors.append("platform is required")
    if not title:
        errors.append("title is required")
    if not item_id and not url:
        errors.append("item_id or url is required")

    hard_constraints = _text_list(raw.get("hard_constraints"))
    if not hard_constraints:
        warnings.append("hard_constraints is empty; confirm product-defining attributes")

    price_basis = raw.get("price_basis")
    if not isinstance(price_basis, dict):
        price_basis = {}
    price_basis = {
        "quantity_included": price_basis.get("quantity_included") or 1,
        "condition": _text(price_basis.get("condition")) or "unknown",
        "shipping": _text(price_basis.get("shipping")) or "unknown",
        "bundle": _text(price_basis.get("bundle")) or "unknown",
    }

    unknowns = _text_list(raw.get("unknowns"))
    if not image_url:
        warnings.append("image_url is missing; image search will be unavailable")
    if raw.get("price") in (None, ""):
        warnings.append("price is missing; price spread cannot be calculated")

    source_card = {
        "item_id": item_id,
        "platform": platform,
        "url": url,
        "title": title,
        "image_url": image_url,
        "price": None if raw.get("price") in (None, "") else str(raw.get("price")),
        "price_basis": price_basis,
        "seller": _text(raw.get("seller") or raw.get("seller_nick")) or None,
        "hard_constraints": hard_constraints,
        "soft_preferences": _text_list(raw.get("soft_preferences")),
        "unknowns": unknowns,
    }
    return {"ok": not errors, "source_card": source_card, "errors": errors, "warnings": warnings}


def _read_json(path: str | None) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize a source product to source_card JSON.")
    parser.add_argument("--input", help="raw source JSON path; defaults to stdin")
    parser.add_argument("--output", help="optional output path; defaults to stdout")
    args = parser.parse_args(argv)

    try:
        result = normalize_source(_read_json(args.input))
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
