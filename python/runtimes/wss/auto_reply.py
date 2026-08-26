"""WSS 入站消息自动回复 — 触发 buyer_reply graph 并经 WS 发出。

在收到买家文本后按 AiSettings 决定是否生成并发送回复。"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from agent.workflows.buyer_reply import run_buyer_reply
from config.settings import AiSettings
from crawlers.xianyu.ws.client import XianyuWsClient
from runtime.observability import get_runtime_observability, track_workflow

logger = logging.getLogger("dingda.runtimes.wss.auto_reply")


async def maybe_auto_reply(
    client: XianyuWsClient,
    *,
    event: dict[str, Any],
    ai_settings: AiSettings | None,
    emit: Any,
) -> None:
    """入站 message 事件：生成回复、发送、并追加 outbound 供 Rust poll。"""
    if event.get("type") != "message":
        return
    if ai_settings is None or not ai_settings.ai_enabled:
        return

    content = str(event.get("content") or "").strip()
    cid = str(event.get("cid") or "").strip()
    peer_id = str(event.get("peer_id") or "").strip()
    if not content or not cid or not peer_id:
        return

    inbound = {
        "content": content,
        "peer_name": event.get("peer_name") or "",
        "item_id": event.get("item_id") or "",
        "item_title": event.get("item_title") or "",
        "history": "",
        "bargain_count": 0,
    }

    try:
        with track_workflow(
            "buyer_reply",
            detail=f"account={client.account_id} cid={cid}",
        ) as run:
            run.stage("graph")
            # 暂不接逐步 on_step（比价图先用）；需要时恢复下面回调并传给 run_buyer_reply
            # def on_step(name, status, *, index=0, total=0, label="", detail=""):
            #     if status == "running":
            #         run.stage(label or name)
            #     elif status == "error":
            #         run.stage(f"error:{label or name}")
            reply = await asyncio.to_thread(run_buyer_reply, ai_settings, inbound)
    except Exception:  # noqa: BLE001
        get_runtime_observability().record_error(
            path="/v1/ws/auto_reply",
            message=f"graph failed account={client.account_id} cid={cid}",
        )
        logger.exception("auto_reply graph 失败 account=%s cid=%s", client.account_id, cid)
        return

    if not reply:
        return

    try:
        await client.send_text(cid, peer_id, reply)
    except Exception:  # noqa: BLE001
        logger.exception("auto_reply 发送失败 account=%s cid=%s", client.account_id, cid)
        return

    message_id = f"xianyu-{uuid.uuid4().hex[:12]}"
    await emit(
        {
            "type": "outbound",
            "account_id": client.account_id,
            "cid": cid,
            "peer_id": peer_id,
            "content": reply,
            "message_id": message_id,
            "in_reply_to": content,
        },
    )
    logger.info("auto_reply 已发送 account=%s cid=%s", client.account_id, cid)
