"""IPC 路由表与 handler 注册 — Contract 路径 → Python handler。

HTTP 与共享内存传输共用同一 ROUTES/HANDLERS，保证行为一致。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dingda_sidecar.runtime.agent.handlers import (
    handle_agent_complete,
    handle_agent_ping,
    handle_agent_reply,
)
from dingda_sidecar.runtime.handlers.ai_probe import (
    handle_ai_account_balance,
    handle_ai_list_models,
    handle_ai_probe_key,
    handle_ai_providers_catalog,
)
from dingda_sidecar.runtime.handlers.channel.cookie_renew import handle_cookie_renew
from dingda_sidecar.runtime.handlers.channel.login_probe import handle_login_probe
from dingda_sidecar.runtime.handlers.channel.qr import (
    handle_qr_cancel,
    handle_qr_check,
    handle_qr_start,
)
from dingda_sidecar.runtime.handlers.channel.search import handle_search
from dingda_sidecar.runtime.handlers.channel.sessions_batch import handle_sessions_batch
from dingda_sidecar.runtime.handlers.copilot import handle_copilot_http_info
from dingda_sidecar.runtime.handlers.xianyu_mtop import (
    handle_xianyu_item_detail,
    handle_xianyu_message_headinfo,
    handle_xianyu_seller_items,
    handle_xianyu_user_profile,
)
from dingda_sidecar.runtime.langgraph.handlers import (
    handle_agent_run_cancel,
    handle_agent_run_control,
    handle_agent_run_start,
    handle_agent_run_status,
)
from dingda_sidecar.runtime.wss.handlers import (
    handle_ws_connect,
    handle_ws_disconnect,
    handle_ws_events_poll,
    handle_ws_history,
    handle_ws_send,
    handle_ws_status,
)

Handler = Callable[..., Any]

ROUTES: dict[str, tuple[str, str]] = {
    "/v1/channel/cookie_renew": ("POST", "handle_cookie_renew"),
    "/v1/channel/qr_start": ("POST", "handle_qr_start"),
    "/v1/channel/qr_check": ("POST", "handle_qr_check"),
    "/v1/channel/qr_cancel": ("POST", "handle_qr_cancel"),
    "/v1/channel/search": ("POST", "handle_search"),
    "/v1/channel/login_probe": ("POST", "handle_login_probe"),
    "/v1/channel/sessions_batch": ("POST", "handle_sessions_batch"),
    "/v1/channel/xianyu/seller_items": ("POST", "handle_xianyu_seller_items"),
    "/v1/channel/xianyu/item_detail": ("POST", "handle_xianyu_item_detail"),
    "/v1/channel/xianyu/user_profile": ("POST", "handle_xianyu_user_profile"),
    "/v1/channel/xianyu/message_headinfo": ("POST", "handle_xianyu_message_headinfo"),
    "/v1/agent/ping": ("POST", "handle_agent_ping"),
    "/v1/agent/complete": ("POST", "handle_agent_complete"),
    "/v1/agent/reply": ("POST", "handle_agent_reply"),
    "/v1/agent/run/start": ("POST", "handle_agent_run_start"),
    "/v1/agent/run/control": ("POST", "handle_agent_run_control"),
    "/v1/agent/run/status": ("POST", "handle_agent_run_status"),
    "/v1/agent/run/cancel": ("POST", "handle_agent_run_cancel"),
    "/v1/ai/probe_key": ("POST", "handle_ai_probe_key"),
    "/v1/ai/account_balance": ("POST", "handle_ai_account_balance"),
    "/v1/ai/providers_catalog": ("POST", "handle_ai_providers_catalog"),
    "/v1/ai/list_models": ("POST", "handle_ai_list_models"),
    "/v1/copilot/http_info": ("POST", "handle_copilot_http_info"),
    "/v1/ws/connect": ("POST", "handle_ws_connect"),
    "/v1/ws/disconnect": ("POST", "handle_ws_disconnect"),
    "/v1/ws/send": ("POST", "handle_ws_send"),
    "/v1/ws/status": ("POST", "handle_ws_status"),
    "/v1/ws/events/poll": ("POST", "handle_ws_events_poll"),
    "/v1/ws/history": ("POST", "handle_ws_history"),
}

HANDLERS: dict[str, Handler] = {
    "handle_cookie_renew": handle_cookie_renew,
    "handle_qr_start": handle_qr_start,
    "handle_qr_check": handle_qr_check,
    "handle_qr_cancel": handle_qr_cancel,
    "handle_search": handle_search,
    "handle_login_probe": handle_login_probe,
    "handle_sessions_batch": handle_sessions_batch,
    "handle_xianyu_seller_items": handle_xianyu_seller_items,
    "handle_xianyu_item_detail": handle_xianyu_item_detail,
    "handle_xianyu_user_profile": handle_xianyu_user_profile,
    "handle_xianyu_message_headinfo": handle_xianyu_message_headinfo,
    "handle_agent_ping": handle_agent_ping,
    "handle_agent_complete": handle_agent_complete,
    "handle_agent_reply": handle_agent_reply,
    "handle_agent_run_start": handle_agent_run_start,
    "handle_agent_run_control": handle_agent_run_control,
    "handle_agent_run_status": handle_agent_run_status,
    "handle_agent_run_cancel": handle_agent_run_cancel,
    "handle_ai_probe_key": handle_ai_probe_key,
    "handle_ai_account_balance": handle_ai_account_balance,
    "handle_ai_providers_catalog": handle_ai_providers_catalog,
    "handle_ai_list_models": handle_ai_list_models,
    "handle_copilot_http_info": handle_copilot_http_info,
    "handle_ws_connect": handle_ws_connect,
    "handle_ws_disconnect": handle_ws_disconnect,
    "handle_ws_send": handle_ws_send,
    "handle_ws_status": handle_ws_status,
    "handle_ws_events_poll": handle_ws_events_poll,
    "handle_ws_history": handle_ws_history,
}
