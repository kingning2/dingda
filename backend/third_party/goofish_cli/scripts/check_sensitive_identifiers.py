#!/usr/bin/env python3
"""Reject account- and conversation-scoped identifiers in tracked text files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

RULES = (
    (
        "sensitive field contains a concrete identifier",
        re.compile(
            r"(?i)(?<![\w])[\"']?(?:unb|tracknick|cid|toid|sessionId|userId|"
            r"send_user_id|senderUserId|peer_user_id|mid|msg_id)[\"']?\s*"
            r"(?::|=)\s*[\"']?(?:\d{8,}|xy\d{6,})(?!\d)"
        ),
    ),
    (
        "sensitive cookie contains a concrete identifier",
        re.compile(r"(?i)[\"'](?:unb|tracknick)[\"']\s*,\s*[\"'](?:\d{8,}|xy\d{6,})[\"']"),
    ),
    ("concrete tracknick identifier", re.compile(r"\bxy\d{8,}\b", re.IGNORECASE)),
    (
        "device identifier uses a concrete account identifier",
        re.compile(r"\bgenerate_device_id\([\"']\d{8,}[\"']\)"),
    ),
    ("raw Xianyu message identifier", re.compile(r"\b\d{10,}\.PNM\b")),
    ("numeric Xianyu conversation identifier", re.compile(r"\b\d{8,}@goofish\b")),
    (
        "message send command contains concrete identifiers",
        re.compile(r"(?i)\bgoofish\s+message\s+send\s+\d{8,}\s+\d{8,}\b"),
    ),
)


def scan_text(text: str) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for description, pattern in RULES:
        for match in pattern.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            findings.append((line_number, description))
    return findings


def tracked_files(repository: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=repository, text=False
    )
    return [repository / path.decode() for path in output.rstrip(b"\0").split(b"\0") if path]


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    findings: list[str] = []

    for path in tracked_files(repository):
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, description in scan_text(text):
            findings.append(f"{path.relative_to(repository)}:{line_number}: {description}")

    if findings:
        print("Sensitive account or conversation identifiers found:")
        print("\n".join(findings))
        print("Replace concrete values with explicit <masked-...> or test placeholders.")
        return 1

    print("No sensitive account or conversation identifiers found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
