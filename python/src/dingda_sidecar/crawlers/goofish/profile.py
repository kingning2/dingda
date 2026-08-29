"""闲鱼用户资料 / 会话商品头信息（mtop）。

拉取卖家/买家资料与会话头图文，供客服上下文与 IPC 查询。"""

from __future__ import annotations

from typing import Any

from dingda_sidecar.crawlers.goofish.mtop import MtopClient, MtopRequest


def fetch_user_profile(cookie_str: str) -> tuple[dict[str, str], str]:
    client = MtopClient(cookie_str)
    request = MtopRequest(
        api="mtop.idle.web.user.page.nav",
        version="1.0",
        data={},
    )
    response = client.call(request)
    if not response.success():
        raise RuntimeError(f"用户资料接口未成功: {response.ret}")

    data = response.data() if isinstance(response.data(), dict) else {}
    base = ((data or {}).get("module") or {}).get("base") if isinstance(data, dict) else {}
    if not isinstance(base, dict):
        base = {}
    profile = {
        "display_name": str(base.get("displayName") or "").strip(),
        "avatar_url": str(base.get("avatar") or "").strip(),
    }
    return profile, client.cookie


def fetch_message_headinfo(
    cookie_str: str,
    session_id: str,
    item_id: str,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "sessionId": session_id,
        "sessionType": 1,
    }
    item_id = str(item_id or "").strip()
    if item_id.isdigit():
        data["itemId"] = int(item_id)

    client = MtopClient(cookie_str)
    request = (
        MtopRequest(
            api="mtop.idle.trade.pc.message.headinfo",
            version="1.0",
            data=data,
        )
        .with_get()
        .with_param("spm_cnt", "a21ybx.im.0.0")
    )
    response = client.call(request)
    if not response.success():
        raise RuntimeError(f"message.headinfo 未成功: {response.ret}")
    payload = response.data()
    return payload if isinstance(payload, dict) else {}
