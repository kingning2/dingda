---
name: python-coding
description: 叮答 Python 编码范例。编写或修改 packages-py/ 下 Python 时必须遵循本 Skill 中的示例：文件头、函数注释、多平台插座基类、命名、生命周期日志。少写边界分支。
---

# Python 编码范例（照抄结构）

写 `packages-py/**/*.py` 时**按下面示例的形状写**，不要自创风格。架构分层见 [layers.md](../layers.md)。

---

## 示例 A：文件头 + 函数注释 + 日志

目标路径：`packages-py/channels/src/channels/xianyu/channel.py`（文件夹已是 `xianyu`，文件不要再叫 `xianyu_*.py`）

**文件头必须像 `infrastructure/events/bus.py` 这样写**：一行总述 + `职责：` +（可选）`设计说明：` / `使用示例：` / 后续备注。禁止只有一句话就结束。

```python
"""闲鱼扫码登录 Channel。

职责：
    启动后台扫码任务、轮询登录进度、成功后导出 cookie。
    供账号域 / HTTP 轮询接口调用，不直接碰 Playwright。

设计说明：
    - 实现 ``QrLoginChannel`` 插座；平台特例只留在本包
    - runtime 句柄只给 ``snapshot`` 轮询用，不持久化

使用示例：
    channel = XianyuQrChannel()
    runtime = channel.start_login(timeout=120)
    snap = channel.snapshot(runtime)
"""

from __future__ import annotations

import logging
from typing import Any

from src.channels.base import QrLoginChannel
from src.channels.types import LoginSnapshot

logger = logging.getLogger("dingda.channel.xianyu")


class XianyuQrChannel(QrLoginChannel):
    """闲鱼插头：实现扫码登录插座上的 start_login / snapshot。"""

    platform = "xianyu"

    def start_login(self, *, timeout: int = 120) -> Any:
        """拉起闲鱼扫码后台任务，返回可供 snapshot 轮询的 runtime。"""
        logger.info("qr login start timeout=%s", timeout)
        runtime = self._spawn(timeout=timeout)
        logger.info("qr login spawned")
        return runtime

    def snapshot(self, runtime: Any) -> LoginSnapshot:
        """把当前扫码进度收成前端可轮询的 LoginSnapshot。"""
        snap = self._read(runtime)
        logger.info("qr login poll status=%s", snap.status)
        if snap.status == "success":
            logger.info("qr login done account_id=%s", snap.account_id)
        return snap
```

### 错误示范（禁止）

```python
# ❌ 文件头只有一句话，缺「职责 / 设计说明」
"""闲鱼扫码登录 Channel：启动后台任务。"""

# ❌ 无文件头、无函数说明、无日志
class XianyuQrChannel:
    def start_login(self, timeout=120):
        return self._spawn(timeout)

# ❌ 文件名重复文件夹：channels/xianyu/xianyu_channel.py
# ❌ 文件名含糊：channels/xianyu/utils.py、helper.py
```

---

## 示例 B：多平台插座（基类 + 插头 + registry）

### 插座 — `packages-py/channels/src/channels/base.py`

```python
"""扫码登录渠道插座。

职责：
    定义各平台 Channel 必须实现的统一接口（start_login / snapshot）。

设计说明：
    - 平台插头放在 ``channels/<platform>/channel.py``，经 registry 按名创建
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from src.channels.types import LoginSnapshot


class QrLoginChannel(ABC):
    """扫码登录插座：start_login → 轮询 snapshot。"""

    platform: ClassVar[str]

    @abstractmethod
    def start_login(self, *, timeout: int) -> Any:
        """启动平台登录任务，返回 runtime 句柄。"""

    @abstractmethod
    def snapshot(self, runtime: Any) -> LoginSnapshot:
        """读取当前登录快照供 HTTP 轮询。"""
```

### 插头 — `packages-py/channels/src/channels/xiaohongshu/channel.py`

```python
"""小红书扫码登录 Channel。

职责：
    对接小红书登录态与快照轮询，实现 QrLoginChannel 插座。
"""

from __future__ import annotations

import logging
from typing import Any

from src.channels.base import QrLoginChannel
from src.channels.types import LoginSnapshot

logger = logging.getLogger("dingda.channel.xiaohongshu")


class XiaohongshuQrChannel(QrLoginChannel):
    """小红书插头。"""

    platform = "xiaohongshu"

    def start_login(self, *, timeout: int = 120) -> Any:
        """启动小红书扫码任务。"""
        logger.info("qr login start timeout=%s", timeout)
        return self._spawn(timeout=timeout)

    def snapshot(self, runtime: Any) -> LoginSnapshot:
        """读取小红书扫码快照。"""
        snap = self._read(runtime)
        logger.info("qr login poll status=%s", snap.status)
        return snap
```

### 注册 — `packages-py/channels/src/channels/registry.py`

```python
"""扫码 Channel 注册表。

职责：
    按 platform 名取出对应插头，避免业务里写 if platform。
"""

from __future__ import annotations

from src.channels.base import QrLoginChannel
from src.channels.xianyu.channel import XianyuQrChannel
from src.channels.xiaohongshu.channel import XiaohongshuQrChannel
from src.shared.errors import AppError

_CHANNELS: dict[str, type[QrLoginChannel]] = {
    "xianyu": XianyuQrChannel,
    "xiaohongshu": XiaohongshuQrChannel,
}


def create_qr_login_channel(platform: str) -> QrLoginChannel:
    """按平台名创建对应扫码 Channel，避免业务里写 if platform。"""
    cls = _CHANNELS.get(platform)
    if cls is None:
        raise AppError("channel.qr_unsupported", f"不支持的平台：{platform}")
    return cls()
```

### 错误示范（禁止）

```python
# ❌ 没有基类，到处 if
def start_login(platform: str, timeout: int):
    if platform == "xianyu":
        ...
    elif platform == "xiaohongshu":
        ...

# ❌ 平台特例塞进 core
# packages-py/crawler/src/crawler/core/xianyu_special_case.py
```

## 示例 C：爬虫插座（基类管浏览器会话，平台只写业务）

**基类管一次：** context / 代理 / 指纹 / 开关页。  
**平台只写：** 打开哪个 URL、怎么抽商品。  
**禁止：** 每个平台 crawler 里再抄一套 launch。

### 插座 — `packages-py/crawler/src/crawler/core/base.py`

```python
"""爬虫浏览器会话基类。

职责：
    统一 context、代理、指纹与开关页；各平台 Source 只写页面与解析。

设计说明：
    - 禁止平台 crawler 自己 launch 浏览器
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.browser.port import BrowserPort, Page
from src.crawler.core.types import CrawlContext, CrawlResult

logger = logging.getLogger("dingda.crawler.base")


@dataclass(frozen=True)
class BrowserSessionOptions:
    """一次抓取的浏览器策略（由调用方传入，基类负责落到 BrowserPort）。"""

    proxy_url: str | None = None
    fingerprint_profile: str | None = None
    cookies: dict[str, str] | None = None


class BrowserCrawler(ABC):
    """爬虫插座：打开/关闭带代理与指纹的 page；子类只实现平台抓取。"""

    platform: str

    def __init__(self, browser: BrowserPort, options: BrowserSessionOptions | None = None) -> None:
        self._browser = browser
        self._options = options or BrowserSessionOptions()

    async def open_page(self, ctx: CrawlContext) -> Page:
        """按代理/指纹策略打开一页，给平台抓取用。"""
        logger.info(
            "browser session open platform=%s proxy=%s fingerprint=%s task=%s",
            self.platform,
            bool(self._options.proxy_url),
            self._options.fingerprint_profile,
            ctx.task_id,
        )
        page = await self._browser.open(
            proxy=self._options.proxy_url,
            fingerprint=self._options.fingerprint_profile,
            cookies=self._options.cookies,
        )
        return page

    async def close_page(self, page: Page) -> None:
        """关闭本轮抓取页。"""
        logger.info("browser session close platform=%s", self.platform)
        await page.close()

    @abstractmethod
    async def search(self, ctx: CrawlContext, query: str) -> CrawlResult:
        """平台搜品：子类实现；开关页必须走 open_page/close_page。"""
```

### 插头 — `packages-py/crawler/src/crawler/sources/xianyu/crawler.py`

```python
"""闲鱼搜品 Source。

职责：
    继承 BrowserCrawler，只写闲鱼搜索页导航与解析；开关页走基类。
"""

from __future__ import annotations

import logging

from src.crawler.core.base import BrowserCrawler
from src.crawler.core.types import CrawlContext, CrawlResult
from src.crawler.sources.xianyu.extractor import extract_search

logger = logging.getLogger("dingda.crawler.xianyu")

SEARCH_URL = "https://www.goofish.com/search"


class XianyuCrawler(BrowserCrawler):
    """闲鱼插头：复用基类浏览器会话，不自己 launch。"""

    platform = "xianyu"

    async def search(self, ctx: CrawlContext, query: str) -> CrawlResult:
        """按关键词抓取闲鱼搜索列表。"""
        logger.info("search start query=%s task=%s", query, ctx.task_id)
        page = await self.open_page(ctx)
        try:
            await page.goto(SEARCH_URL, params={"q": query})
            logger.info("search fetched url=%s", SEARCH_URL)
            raw = await page.content()
            items = extract_search(raw)
            logger.info("search done count=%s", len(items))
            return CrawlResult(items=items)
        except Exception:
            logger.exception("search failed query=%s", query)
            raise
        finally:
            await self.close_page(page)
```

### 错误示范（禁止）

```python
# ❌ 每个平台自己 launch + 代理 + 指纹
async def search(...):
    from camoufox.async_api import AsyncCamoufox
    async with AsyncCamoufox(proxy=...) as browser:
        ...

# ❌ 基类里写闲鱼 URL / 商品解析
class BrowserCrawler:
    async def search_xianyu(self, query: str): ...
```

少纠结边界：代理/指纹缺省就走默认配置并打日志，不要为每种代理协议写三层校验。

---

## 命名速查

| 位置 | 正确 | 错误 |
|------|------|------|
| `channels/xianyu/` | `channel.py` `login.py` | `xianyu_channel.py` `xianyu_lib.py` |
| `crawler/core/` | `base.py` | `browser_crawler_base_impl.py` |
| `crawler/sources/ali1688/` | `crawler.py` `extractor.py` | `ali1688_crawler.py` `helpers.py` |
| `browser/adapters/` | `camoufox.py` | `camoufox_adapter_impl.py` |

---

## 目录 README（树形，上层引用下层）

每个**有代码的文件夹**必须有 `README.md`。`__pycache__` 不要写。

形状照抄 `packages-py/api/src/api/README.md`：

1. 一行总述本目录职责
2. **本目录文件**：每个 `.py` 单独一小节（或条目），写清：干什么、关键函数/类、谁调用。有 `app.py` 必须写透
3. **子目录**：用相对链接指向下层 `README.md`，不要把子目录每个文件抄进上层
4. 禁止另起一套地图；文件级细节以下层 README 为准

不要只写「`foo.py` — 扫码」。读者没看过代码也要能知道该打开哪个文件。


```markdown
# api

产品 HTTP 路由。

## 本目录文件

- `router.py` — 聚合各路由挂到 `/v1`

## 子目录

无。
```

上层引用下层（如 `packages-py/crawler/src/crawler/README.md`）：

```markdown
## 子目录

- [core/](core/README.md) — 采集核心
- [sources/](sources/README.md) — 各平台 Source
- [extraction/](extraction/README.md) — 抽取与修复
```

新增目录时：**先写下层 README，再在上层「子目录」里加一行链接**。改职责时同步该层 README，不要只改注释。

---

## 检查清单（交代码前）

- [ ] 文件顶有模块 docstring（一行总述 + `职责：`，照抄 `bus.py` / 示例 A）
- [ ] 每个函数有「解决什么问题」的 docstring
- [ ] 多平台有基类 + registry，无散落 `if platform`
- [ ] 爬虫平台继承 `BrowserCrawler`（或同等基类），未重复实现代理/指纹/context
- [ ] 文件名不重复文件夹名，且一眼能懂
- [ ] 业务方法有 start / 关键 / done|failed 日志
- [ ] 没有为大边界情况堆防御代码
- [ ] 本目录有 `README.md`；上层 README 已链接到本目录
