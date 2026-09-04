---
name: browser-architecture
description: 约束叮答 Browser 基础设施与适配器。开发或修改浏览器生命周期、Context、Page、Cookie、导航、DOM、Playwright、Camoufox、CDP 时使用。禁止 Browser 包含商品模型或 Agent 推理；禁止 Agent/Crawler 直接 import Playwright 或 Camoufox。
---

# Browser 架构开发规范

先读 [layers.md](../layers.md)（含**核心规则**原文）。Browser 必须独立于 Crawler。它是执行基础设施，不是业务逻辑。

## 核心规则（本层相关）

- Browser = 浏览器能力层，只负责启动、Context、Page、导航、点击、输入、Cookie、Session、截图、网络监听等通用能力。
- Browser 禁止出现 Xianyu、1688、商品、价格等平台业务逻辑。
- Crawler 禁止直接依赖 Playwright / Camoufox，必须依赖 Browser Interface。
- 浏览器新增只修改 `browser/adapters/<browser>/`；平台新增只修改 `crawler/sources/<platform>/`。
- 登录/账号语义属于 `channels/<platform>/`，Browser 只负责通用 Session/Cookie 能力。
- Agent / MCP / Tool 不得直接操作 Playwright/Camoufox，统一通过 Tool → Crawler → Browser。
- 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。

## 何时必须遵守

- 启动/关闭浏览器、Context、Page、Session
- Cookie 注入与导出、导航、点击、填表、等网络
- 新增 Playwright / Camoufox / CDP / Chromium 实现
- 修改 `browser/adapters/`、`browser/sync.py`、`browser/slider.py`

## 目标目录

```text
server/src/browser/
├── manager.py
├── session.py
├── context.py
├── page.py              # Playwright 协议的 Page 包装（操作层）
├── sync.py              # Channel 扫码线程同步开页
├── slider.py            # 滑块交互原语
└── adapters/
    └── camoufox.py      # 浏览器：Camoufox
```

以后新增**浏览器**只加 adapter，例如 `adapters/firefox.py`。

Channel 登录经 `browser/sync` / `BrowserManager` 开页；闲鱼 Cookie 域名在 `channels/xianyu/cookies.py`。

## 只负责

* Browser lifecycle
* Context
* Page
* Session
* Cookie
* Navigation
* DOM interaction
* Network interaction

## 不负责

* 商品业务模型
* 商品价格计算
* Agent reasoning
* Snapshot business logic（原始字节可从 page/response 取出，**是否当业务快照持久化**由 Crawler `snapshot/` 决定）

## 与 Crawler 基类的分工

```text
browser/page.py           操作层：Playwright 协议的 Page（goto/click/cookie）
browser/adapters/*        浏览器插头（Camoufox）：启动哪一种浏览器
crawler/core/base.py      爬虫插座：代理 / 指纹 / context 策略，调 BrowserPort
sources/<platform>/       平台插头：只写业务页与解析
```

- 指纹、代理的**引擎参数**由 Browser Adapter 执行。
- **何时用哪套代理/指纹**由 `BrowserCrawler`（爬虫基类）统一处理，平台 Source 不要各自 launch。
- 详见 [crawler-architecture](../crawler-architecture/SKILL.md) 与 [python-coding](../python-coding/SKILL.md) 示例 C。

## 依赖

Crawler 可以使用 Browser。

但是：

```text
Agent → Playwright
```

属于禁止架构。

应该：

```text
Agent
 ↓
BrowserTool
 ↓
Browser
 ↓
CamoufoxAdapter
```

Crawler Source 同样只依赖 Browser **接口**（Port），不 import `adapters.camoufox`。

```text
Browser Interface
    ↑
CamoufoxAdapter
```

Channel 扫码可以经同一 Browser Port 开页；不要每个 Channel 自己 `async_playwright().start()`。

## 新增浏览器

如果以后新增 Camoufox / 其它浏览器：

```text
browser/
└── adapters/
    └── camoufox.py
```

不能让 Agent / Crawler 直接 import 具体实现。

清单：

1. 实现现有 Browser 接口（launch / context / page / cookies / goto / click / close）
2. 只在 `adapters/<name>.py` + registry 注册
3. 不改 Agent；不改 Crawler Core；Source 不出现 `from camoufox...`
4. 适配器内禁止出现「闲鱼商品」「价格」「店铺」等业务类型
5. 测试 mock 接口，而不是在单测里硬绑真实浏览器（集成测试可标 `@pytest.mark.integration`）

## 错误示例

```python
from playwright.async_api import async_playwright

class Agent:
    async def search(self):
        browser = await async_playwright().start()
```

```python
# ❌ Crawler 绑定实现
from camoufox.sync_api import Camoufox

class XianyuCrawler:
    def search(self):
        with Camoufox(headless=True) as browser:
            ...
```

```python
# ❌ Adapter 里的业务
def extract_product_price(page) -> Product:
    ...
```

## 正确示例

```text
Agent
 ↓
CrawlerTool
 ↓
Crawler
 ↓
BrowserPort
 ↓
CamoufoxAdapter
```

```python
# ✅ Source 只拿 Port
async def search(ctx: CrawlContext, browser: BrowserPort, query: str) -> CrawlResult:
    page = await browser.open(ctx.session)
    await page.goto(SEARCH_URL)
    html = await page.content()
    return extract_search(html)
```

## Channel 与 Browser

Channel 扫码经 `browser.sync.sync_headless_page` 或 `BrowserManager` 开页；闲鱼 cookie 域名映射属于 **xianyu Channel**（`channels/xianyu/cookies.py`），不是 Browser adapter 的职责。

## 检查清单

- [ ] 新文件在 `server/src/browser/`（浏览器在 adapters）
- [ ] 无商品模型、无 Agent、无「只存解析后价格」
- [ ] Agent/Crawler/Workflow 未 import playwright/camoufox
- [ ] 新增引擎只加 adapter
- [ ] 未为「打开浏览器」新增 Tauri command
