"""共用节流闸门：同一 key 的两次放行之间至少隔 ``min_interval`` 秒。

职责：
    给平台读操作（详情 / 列表）一个进程级最小间隔，避免连续突发请求把上游打成限流。
    闲鱼详情一次连拉十条就会吃到 ``被挤爆啦,请稍后重试``，之后每条都要走风控恢复。

设计说明：
    - **等，不抛**：闸门只 sleep 补齐差额，不产生错误 —— 调用方拿到的仍是正常结果，只是慢一点。
      这与 ``channels/xianyu/limiter.py`` 的写令牌桶不同：那个是超限即拒（``channel.rate_limited``），
      这个只是排队。
    - **靠「排号」而不是锁**：读改写 ``_next_at`` 中间没有 ``await``，所以天然原子；
      并发调用各自领到一个往后排的号，不会有一批请求同时读到旧时间戳而全部放行。
      也不用 ``asyncio.Lock`` —— 它会在首次 acquire 时绑定事件循环，模块级缓存跨循环复用会炸。
    - key 由调用方给（如 ``xianyu:detail``），间隔多少由平台 Source 决定，这里不做平台判断。
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger("dingda.crawler.pacing")

_next_at: dict[str, float] = {}


async def pace(key: str, *, min_interval: float) -> None:
    """领一个号并等到属于自己的时刻；``min_interval <= 0`` 直接放行。"""
    if min_interval <= 0:
        return
    now = time.monotonic()
    reserved = max(now, _next_at.get(key, 0.0))
    _next_at[key] = reserved + min_interval
    wait = reserved - now
    if wait > 0:
        logger.info("节流等待 key=%s %.2fs", key, wait)
        await asyncio.sleep(wait)
