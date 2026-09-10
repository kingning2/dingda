"""爬虫步骤级恢复钩子。

职责：
    包装单步抓取：遇风控则委托平台 ``RiskRecoverPort``（自动→人工），
    成功后重试该步；登录失效原样上抛给 Tool 层扫码续跑。

设计说明：
    - 平台无关；闲鱼/小红书各自实现 RiskRecoverPort
    - 不 import Playwright；页操作经 BrowserPort Page
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

from src.browser.port import Page
from src.shared.errors import AppError

logger = logging.getLogger("dingda.crawler.recovery")

T = TypeVar("T")


class RiskRecoverPort(Protocol):
    """平台风控恢复插座。"""

    async def recover_risk(
        self,
        page: Page,
        *,
        where: str,
        url: str | None = None,
    ) -> None:
        """自动解风控；失败则有头窗口阻塞等人；仍失败抛 channel.risk。"""


async def run_step(
    name: str,
    fn: Callable[[], Awaitable[T]],
    *,
    page: Page | None = None,
    risk: RiskRecoverPort | None = None,
    is_risk: Callable[[BaseException], bool] | None = None,
    max_retries: int = 2,
) -> T:
    """执行一步；风控则恢复并重试，最多 ``max_retries`` 次额外尝试。"""

    def _default_is_risk(exc: BaseException) -> bool:
        return isinstance(exc, AppError) and exc.code == "channel.risk"

    check = is_risk or _default_is_risk
    attempt = 0
    while True:
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, AppError) and exc.code == "account.session_expired":
                raise
            if not check(exc):
                raise
            if risk is None or page is None or attempt >= max_retries:
                logger.warning(
                    "step risk unrecovered name=%s attempt=%s",
                    name,
                    attempt,
                )
                raise
            attempt += 1
            logger.info(
                "step risk recover name=%s attempt=%s/%s",
                name,
                attempt,
                max_retries,
            )
            await risk.recover_risk(page, where=name, url=getattr(page, "url", None))
