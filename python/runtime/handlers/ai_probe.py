"""AI provider 探测 — API Key / 余额（OpenAI 兼容 + DeepSeek）。

供 Rust `ai_test_api_key` / `ai_account_balance` 转发，避免在 Tauri cmd 里直接 HTTP。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("dingda.runtime.ai_probe")


def _openai_compatible_root(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith(("/v1", "/v2", "/v3")):
        return base
    return f"{base}/v1"


def _uses_deepseek_balance(kind: str | None, base_url: str) -> bool:
    return (kind or "").lower() == "deepseek" or "deepseek.com" in base_url.lower()


def _http_get_json(url: str, api_key: str, *, timeout: float = 15.0) -> tuple[int, Any]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            status = int(getattr(resp, "status", 200) or 200)
            if not body.strip():
                return status, None
            try:
                return status, json.loads(body)
            except json.JSONDecodeError:
                return status, body
    except urllib.error.HTTPError as error:
        return int(error.code), None
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(f"请求失败: {error}") from error


def handle_ai_probe_key(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    del trace_id
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失"}

    base_url = str(payload.get("base_url") or "").strip()
    api_key = str(payload.get("api_key") or "").strip()
    kind = str(payload.get("kind") or "").strip() or None

    if not api_key:
        return {"ok": False, "message": "API Key 为空"}

    try:
        if _uses_deepseek_balance(kind, base_url):
            balance = handle_ai_account_balance(
                {"base_url": base_url, "api_key": api_key},
                trace_id="",
            )
            message = "API Key 可用" if balance.get("ok") else str(balance.get("message") or "")
            return {"ok": bool(balance.get("ok")), "message": message}

        url = f"{_openai_compatible_root(base_url)}/models"
        status, _ = _http_get_json(url, api_key)
        if 200 <= status < 300:
            return {"ok": True, "message": "API Key 可用"}
        return {"ok": False, "message": f"HTTP {status}"}
    except Exception as error:  # noqa: BLE001
        logger.warning("ai_probe_key failed: %s", error)
        return {"ok": False, "message": str(error)}


def handle_ai_account_balance(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    del trace_id
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "is_available": False,
            "balances": [],
            "message": "payload 缺失",
        }

    base_url = str(payload.get("base_url") or "").strip().rstrip("/")
    api_key = str(payload.get("api_key") or "").strip()
    if not api_key:
        return {
            "ok": False,
            "is_available": False,
            "balances": [],
            "message": "API Key 为空",
        }

    try:
        url = f"{base_url}/user/balance"
        status, body = _http_get_json(url, api_key)
        if not (200 <= status < 300):
            return {
                "ok": False,
                "is_available": False,
                "balances": [],
                "message": f"HTTP {status}",
            }
        if not isinstance(body, dict):
            return {
                "ok": False,
                "is_available": False,
                "balances": [],
                "message": "未返回余额信息",
            }
        raw_balances = body.get("balance_infos") or []
        balances: list[dict[str, str]] = []
        if isinstance(raw_balances, list):
            for item in raw_balances:
                if not isinstance(item, dict):
                    continue
                balances.append(
                    {
                        "currency": str(item.get("currency") or ""),
                        "total_balance": str(item.get("total_balance") or ""),
                        "granted_balance": str(item.get("granted_balance") or ""),
                        "topped_up_balance": str(item.get("topped_up_balance") or ""),
                    }
                )
        is_available = bool(body.get("is_available")) if "is_available" in body else bool(balances)
        ok = bool(balances)
        return {
            "ok": ok,
            "is_available": is_available,
            "balances": balances,
            "message": "ok" if ok else "未返回余额信息",
        }
    except Exception as error:  # noqa: BLE001
        logger.warning("ai_account_balance failed: %s", error)
        return {
            "ok": False,
            "is_available": False,
            "balances": [],
            "message": str(error),
        }
