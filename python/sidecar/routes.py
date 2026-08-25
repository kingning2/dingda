"""Sidecar route table — consumed by Rust-managed HTTP server."""

from __future__ import annotations

ROUTES: dict[str, tuple[str, str]] = {}

ROUTES["/v1/channel/cookie_renew"] = ("POST", "handle_cookie_renew")
ROUTES["/v1/channel/qr_start"] = ("POST", "handle_qr_start")
ROUTES["/v1/channel/qr_check"] = ("POST", "handle_qr_check")
ROUTES["/v1/channel/qr_cancel"] = ("POST", "handle_qr_cancel")
ROUTES["/v1/channel/search"] = ("POST", "handle_search")
ROUTES["/v1/channel/login_probe"] = ("POST", "handle_login_probe")
ROUTES["/v1/agent/ping"] = ("POST", "handle_agent_ping")
ROUTES["/v1/agent/reply"] = ("POST", "handle_agent_reply")
