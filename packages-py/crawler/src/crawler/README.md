# crawler

平台**采集**：搜索页、详情、解析成 `CrawlItem`。登录扫码不在这里。

依赖：浏览器平台走 `BrowserPort`；`ali1688` 走 `channels.ali1688` 官方 HTTP（无 Browser）。闲鱼详情会调 `channels.xianyu.mtop`。

禁止：本包 `import playwright` / `camoufox`；禁止在 `core/` 写 goofish 选择器。

## 本目录文件

### `ocr.py`

图片 OCR（RapidOCR）：小红书笔记图文识字，写入详情 `ocr_text`。
依赖 `rapidocr-onnxruntime`（wheel 自带 ONNX 模型）。不在 Server 启动预热；Agent 开跑时后台 `warm_ocr`（与思考并行）。可选脚本 `scripts/prefetch_ocr.py` 仅本地验证安装。

### `registry.py`

- `_BROWSER_SOURCES`：`xianyu` / `xiaohongshu` → `create_crawler(platform, browser, options)`
- `_API_SOURCES`：`ali1688` → `create_api_crawler(platform)`（不强制 Browser）
- `cookies_for` / `list_platforms` / `is_api_platform`

新平台：加 `sources/<id>/` 再在这里登记。

### `selection.py`

选品打分：把抓到的商品行折算成候选品类的 0~100 分与人类可读的理由。**纯函数、无 LLM、无网络。**
放在 crawler 而不是 agent，是因为它必须懂平台语义 —— `want_count` 在闲鱼是「想要人数」、
在小红书是「收藏数」，同一个 key 语义不同，任何跨平台相加都是在算一个没有意义的数。
`EVIDENCE_ROLES` 就是这张角色表：平台差异只在那里分叉，计算里不分叉。

两条诚实性规则：
- 归一化按平台分组，**分数只在同一平台内可比**（每个候选带 `score_scope`）。
- 量不到的维度剔出加权、权重重新归一（不给 0 分），最后再乘一次证据覆盖率 ——
  否则一个只量到「竞争密度」的候选会靠归一化反超四个维度都量到的候选。

输入是 `agent.items.DetailItem` 的 dict，不是 `CrawlItem`：`agent/tools/crawl._ok` 在边界上
就丢掉了 `CrawlItem.raw`，打分器够不着它。

### `service.py`

`CrawlerService`：**骨架**。将来给 `api/crawler` 做任务创建/查询。真正搜品走 Agent 工具
`agent.tools.crawl.search_items` / `fetch_detail`，选品打分走本包的 `selection.py`。

### `__init__.py`

包标记。

## 子目录

- [core/](core/README.md) — `BrowserCrawler` / `ApiCrawler` 与 `CrawlItem`
- [sources/](sources/README.md) — 各平台插头
