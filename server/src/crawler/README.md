# crawler

平台**采集**：搜索页、详情、解析成 `CrawlItem`。登录扫码不在这里。

依赖：`BrowserPort`（经 Manager/registry），闲鱼详情会调 `channels.xianyu.mtop`（HTTP，不是 Playwright）。

禁止：本包 `import playwright` / `camoufox`；禁止在 `core/` 写 goofish 选择器。

## 本目录文件

### `registry.py`

`_SOURCES = {"xianyu": XianyuCrawler, "xiaohongshu": XiaohongshuCrawler}`。`create_crawler(platform, browser, options)` 注入 Port。`cookies_for(platform, cookie)` 按插头转 Cookie。`list_platforms()` 给 Tool/UI。新平台：加 `sources/<id>/` 再在这里登记。

### `service.py`

`CrawlerService`：**骨架**。将来给 `api/crawler` 做任务创建/查询。真正搜品现在走 Tool `search`/`product`，直接 `create_crawler`。

### `__init__.py`

包标记。

## 子目录

- [core/](core/README.md) — 基类与 `CrawlItem`（平台无关）
- [sources/](sources/README.md) — 各平台插头
