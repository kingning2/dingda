---
name: py-flows
description: 叮答 Python 运行链路示例：浏览器从壳到 Page 的起停全链、爬虫从 Agent/HTTP 到 Source 的调用全链。写需要跨包串起来的代码（新爬虫平台接线、浏览器排障、Tool 编排）时使用；单包内怎么写看 py-dev，本文件只讲「链路怎么转」。
---

# 运行链路示例（浏览器起停 + 爬虫调用）

本文件每一段都摘自真实代码（标注文件路径），是「插座模式」（py-dev 2.1）的运转实证。
改链路前先读完，别凭印象接线。

## 0. 两条链一张图

```
浏览器起停链（谁都不许跳过 manager）：
  壳(Rust) 注 DINGDA_CAMOUFOX_EXE
    → pool.acquire() 懒启动（无空闲实例才拉进程）
    → registry.create_browser("camoufox")
    → CamoufoxAdapter.launch() → AsyncCamoufox 进程
    → PooledPort 交给调用方 → 用完 release

爬虫调用链（Agent → Tool → Crawler → BrowserPort，AGENTS.md 2.1 第 2 条的实例）：
  Agent 编排 / HTTP
    → tools/search.py run_search(SearchInput)        # 唯一 Tool 层入口
    → registry.create_crawler(platform, port, ...)   # 工厂，禁 if/else
    → sources/<platform>/crawler.py（BrowserCrawler 插头）
    → crawler/core/base.py open_page() → port.open() → Page
    → finally manager.release(port)
```

## 1. 链路 A：浏览器怎么起

### ① 壳侧注入可执行文件（Rust，可选）

桌面壳启动时把 Camoufox 解压到 `~/.dingda/v2/camoufox/current`，路径注入环境变量
（实证 `packages-rs/python/src/env.rs:53`）：

```rust
env.push(("DINGDA_CAMOUFOX_EXE".into(), exe.display().to_string()));
```

找不到该变量时 Python 侧回退到 camoufox 包自带二进制——Web 联调（无壳）也能跑。

### ② 申请端口：唯一合法入口（任何调用方都长这样）

```python
from browser.manager import get_browser_manager          # 共享单例
from contracts.browser_port import LaunchOptions

manager = get_browser_manager()
port = await manager.acquire(LaunchOptions(headless=True))
```

### ③ 池懒启动（首次 acquire 才拉进程，实证 browser/pool.py）

```python
# pool.acquire()：无空闲实例 → launch_inst.launch(create_browser)
#   —— 把 registry 的工厂函数传给 instance，池不认识具体引擎
# registry.create_browser("camoufox") → CamoufoxAdapter()；未知名抛 AppError
# CamoufoxAdapter.launch()（实证 adapters/camoufox.py）：
#   resolve_camoufox_exe() 读 DINGDA_CAMOUFOX_EXE → AsyncCamoufox(**kwargs).__aenter__()
#   生命周期日志：logger.info("Camoufox 开始启动 headless=… / 启动完成 elapsed=…")
```

### ④ 拿到的是 PooledPort（池内已启动，实证 pool.py:93）

```python
# 「池内已启动；忽略调用方 launch」—— 调用方永远不要自己 launch/close
page = await port.open(                                  # 签名见 contracts/browser_port.py
    proxy=inp.proxy_url,                                 # 仅这几个参数，没有业务概念
    cookies=cookies,                                     # Sequence[Cookie] 或 Mapping
    default_domain="",
)
await page.goto(url, params={...})                       # Page：goto/click/fill/evaluate/cookies/screenshot
```

### ⑤ 用完必还 + 停机收口

```python
finally:
    await manager.release(port)                          # 不还 = 池被占满
```

Server 停机时统一收口（实证 `api/boot/lifespan.py`）：

```python
yield
await get_browser_manager().stop()
close_sync_browser()
```

## 2. 链路 B：爬虫怎么调用（实证 tools/search）

### ① Tool 层入口（Agent 和 HTTP 都经它，谁也不许绕）

```python
async def run_search(inp: SearchInput) -> list[CrawlItem]:
    # 分流（实证：is_api_platform 判断，不是 if platform == "xianyu"）
    if is_api_platform(inp.platform):
        return await _search_api(inp, task_id, query)        # ali1688，无浏览器
    return await _search_browser(...)
```

### ② 浏览器平台全流程（实证 `_search_browser`，这是标准接线）

```python
manager = get_browser_manager()
port = await manager.acquire(LaunchOptions(headless=True))
try:
    options = BrowserSessionOptions(
        proxy_url=inp.proxy_url,
        cookies=cookies_for(platform, cookie),   # Cookie 域名规则在 channels/<platform>/cookies
        cookie_domain=inp.cookie_domain or "",
    )
    crawler = create_crawler(platform, port, options)        # registry 工厂注入插座
    result = await crawler.search(CrawlContext(task_id=task_id, meta=meta), query)
    if platform == "xianyu":                                 # 平台后处理也收在 Tool 层
        items = await _enrich_xianyu_details(crawler, items, ...)
    return list(result.items)
finally:
    await manager.release(port)
```

### ③ API 平台（ali1688，同一套契约、零浏览器）

```python
crawler = create_api_crawler(inp.platform)   # registry._API_SOURCES
result = await crawler.search(CrawlContext(task_id=task_id), query)
```

### ④ Source 实现（范本 sources/xianyu/crawler.py，头注原文）

```python
"""闲鱼 Crawler Source：搜索列表与商品详情。

设计说明：
    - 禁止在本模块 import Playwright / Camoufox，仅经 BrowserPort
    - 过滑块与风控判定属 Channel（slider / risk），不进 Browser
    - 调用方：tools.search / tools.product、crawler/registry
"""

class XianyuCrawler(BrowserCrawler):
    # 构造收 (browser: BrowserPort, options)；search/detail 由 core/base.py 统一调度：
    # open_page(ctx) 拿 Page → 页内 mtop 优先 → DOM 抽取兜底
```

## 3. 新增一个爬虫平台 = 三步（调用方零改动）

1. `crawler/sources/<id>/crawler.py` 实现 `BrowserCrawler`（或 API 平台实现 `ApiCrawler`）；
2. `crawler/registry.py` 对应表（`_BROWSER_SOURCES` / `_API_SOURCES`）加一行；
3. 完——`tools.search` 的 `platform` 参数天然开放，Agent/HTTP 无需改。

浏览器引擎同理：`adapters/<name>.py` 实现 `BrowserPort` → `browser/registry.py` 加一行。

## 4. 越链 = 违规（反例清单）

```python
# ① api/domains 里直接 acquire 浏览器 —— 浏览器只允许 Tool 层申请
# ② Source 里 import Playwright / 自己 launch —— 只经 BrowserPort
# ③ 业务里 if platform == "xianyu": crawler = XianyuCrawler(...) —— 必须走 registry
# ④ 用完不 release —— 池有上限（pool_max_browsers），泄漏即全局卡死
# ⑤ Cookie 域名/拼装规则写进 Browser adapter —— 归 channels/<platform>/cookies
# ⑥ 滑块/风控逻辑写进 Source 或 Browser —— 归 channels/<platform>/{risk,slider}
```

排障入口：进程没起 → 查 ①②；acquire 卡住 → 查 ④ 池占用；页面打不开 →
先看 adapter 生命周期日志（elapsed=…），再查 cookie/proxy 注入链（②→④）。
