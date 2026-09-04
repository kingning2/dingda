---
name: crawler-architecture
description: 约束叮答 Crawler 模块目录与平台扩展方式。开发或修改爬虫、闲鱼/1688/淘宝/Amazon/小红书抓取、解析、snapshot、去重、CrawlTask 时使用。禁止把平台特例写入 crawler/core 或 agent，禁止 Crawler 包含 Agent 决策，禁止 crawler 直接当 Playwright 入口。
---

# Crawler 架构开发规范

先读 [layers.md](../layers.md)（含**核心规则**原文）。Crawler 负责「按任务抓取并产出结构化结果 + 原始快照」，不负责 Agent 推理。

## 核心规则（本层相关）

- Crawler = 平台采集层，只负责闲鱼/1688等平台的搜索、详情、解析、标准化、Snapshot、Dedup。
- Crawler 禁止直接依赖 Playwright / Camoufox，必须依赖 Browser Interface。
- 平台新增只修改 `crawler/sources/<platform>/`，浏览器新增只修改 `browser/adapters/<browser>/`。
- 登录/账号语义属于 `channels/<platform>/`，Browser 只负责通用 Session/Cookie 能力。
- Agent / MCP / Tool 不得直接操作 Playwright/Camoufox，统一通过 Tool → Crawler → Browser。
- 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。

## 何时必须遵守

- 实现搜索/详情/列表抓取
- 新增或修改一个电商平台
- 解析 HTML/JSON、规范化商品字段
- 保存快照、去重、任务幂等
- Review `domains/crawler`、未来的 `server/src/crawler/`

## 目标目录

```text
server/src/crawler/
├── core/
├── sources/
├── extraction/
├── snapshot/
└── dedup/
```

| 目录 | 负责 |
|------|------|
| `core/` | CrawlContext、Request/Response、CrawlTask/Result、**BrowserCrawler 基类（插座）**、lifecycle |
| `sources/` | 平台插头（继承基类，只写平台抓取/解析） |
| `extraction/` | raw → parser → extractor → normalizer |
| `snapshot/` | 原始抓取快照 |
| `dedup/` | URL / 商品 / Snapshot / task 幂等 |

## 爬虫也是插座（必遵）

多平台抓取**必须**有基类，统一管浏览器会话，平台不要各自再写一遍：

```text
BrowserCrawler（插座 / 基类）
  · 向 BrowserPort 要 context / page
  · 代理、指纹、cookie 注入、开关页
  · 统一 start / 轮询或翻页 / done 日志骨架
        ↑
sources/xianyu/crawler.py
sources/ali1688/crawler.py
sources/xiaohongshu/crawler.py
```

- **基类放** `crawler/core/base.py`（或 `session.py`），只依赖 `browser` **接口**，不 `import playwright` / `camoufox`。
- **平台插头**只实现搜品/详情/解析；打开浏览器、设代理、设指纹调用基类方法。
- **禁止**每个 `sources/<p>/crawler.py` 里复制一套 launch + proxy + fingerprint。
- 指纹/代理的**引擎实现**仍在 `browser/adapters/`；基类只传策略（proxy url、fingerprint profile id）。

完整示例见 [python-coding/SKILL.md](../python-coding/SKILL.md) 示例 C。

现存 `server/src/domains/crawler/service.py` 是空骨架。**新代码不要往这里堆。**  

前端手动搜品走 `POST /v1/crawler/...`（见 `src/contracts/crawler.ts`），**不经产品 Agent**。Agent 搜品必须走同名 Crawler Tool，最后仍进同一套 `crawler/`。MCP（`dingda-mcp`）同样只能打到这套 Core，禁止再包一层 goofish 特例。

## sources

```text
sources/
├── xianyu/
├── ali1688/
├── taobao/
├── amazon/
└── xiaohongshu/     # 若做商品/笔记抓取；登录仍留在 channels/
```

每个平台原则上：

```text
xianyu/
├── crawler.py      # 继承 BrowserCrawler，只写闲鱼抓取
├── extractor.py
├── models.py
└── ...
```

平台特有逻辑必须放在 Source 内；浏览器上下文/代理/指纹复用 `core` 基类。

禁止：

```text
crawler/core/
    xianyu_special_case.py
```

或者：

```text
agent/
    xianyu_logic.py
```

`server/src/channels/xianyu/` 只保留登录/cookie/风控恢复。不要在 Channel 里写搜品列表。

## extraction

```text
raw response
    ↓
parser
    ↓
extractor
    ↓
normalizer
```

- `parser`：字节/HTML/JSON → 可遍历结构
- `extractor`：平台字段抽出
- `normalizer`：变成跨平台商品字段（给前端 / Agent 的 `CrawlResult`）

Normalizer 可以住在 `extraction/`；平台字段名只出现在对应 `sources/<p>/`。

## snapshot

原始快照与业务结构化数据必须分离。

不要只保留经过 AI / Parser 处理后的结果。

快照至少能回答：这次请求的 URL、状态、原始 body/headers、时间、task id。存取经 Snapshot Port，不在 Source 里直接写 sqlite。

## dedup

负责：

* URL 去重
* 商品去重
* Snapshot 去重
* Crawl task 幂等

不要让 Agent 自己实现去重。不要把去重规则复制进每个 Source（Source 只提供去重键，如 platform item id）。

## 依赖

```text
Crawler Core  ←  Source Adapter
     ↓
Browser Port  →  browser adapters
```

允许：

- `crawler.core` 定义 Port（Browser、SnapshotStore）
- `sources/<p>` import `crawler.core`、`crawler.extraction` 接口、`src.browser` **接口**

禁止：

- `crawler.core` import 某个 `sources.xianyu`
- Crawler import `src.agent`
- `crawler/playwright.py` 或 Source 里 `from playwright.async_api import async_playwright`
- Crawler 直接 `sqlite3`
- 在 Crawler 里做 LLM planning / tool selection

## 新增平台（标准流程）

若新增 `Ali1688`：

```text
crawler/
└── sources/
    └── ali1688/
        ├── crawler.py
        ├── extractor.py
        ├── models.py
        └── ...
```

而不是修改：

```text
agent/core/
crawler/core/
browser/
```

除非确实需要扩展公共抽象（例如所有平台都缺「店铺」字段，才改 `CrawlResult`）。

清单：

1. 建 `sources/<id>/`，平台逻辑只放这里
2. 实现 Core 的 Source 接口（search / detail 以实际 Port 为准）
3. 原始响应进 `snapshot/`，结构化结果进 `CrawlResult`
4. 提供去重键给 `dedup/`
5. 在 Source registry 注册
6. 需要登录时 **复用** `channels/` 已有 session，不要复制扫码
7. 加 `server/tests/crawler/sources/<id>/`
8. 更新契约里的 platform 枚举（Python + `src/contracts/crawler.ts`）
9. **不改** Agent Core；Tool 若已有 `platform` 字段则不必改 Tool

## 错误 / 正确

```text
❌ crawler/playwright.py
❌ crawler/core/xianyu_special_case.py
❌ Agent 里写去重
❌ 只存 normalizer 后的 JSON，丢掉原始 HTML/API body
```

```text
✅ sources/xianyu/crawler.py 继承 BrowserCrawler，只写闲鱼页
✅ core/base.py 统一代理 / 指纹 / context
✅ 手动 UI、产品 Agent、MCP 三条入口汇合到同一 Crawler Core
```

## 检查清单

- [ ] 平台代码在 `sources/<id>/`，不在 core/agent/browser
- [ ] 平台 crawler 继承 `BrowserCrawler`（或同等基类），未各自 launch / 设代理指纹
- [ ] 未直接 import Playwright/Camoufox
- [ ] 有原始 snapshot，且与结构化数据分离
- [ ] 去重在 `dedup/`，不在 Agent
- [ ] 无规划/推理/LLM 调用
- [ ] 产品入口是 Python HTTP，不是新的 Tauri command
