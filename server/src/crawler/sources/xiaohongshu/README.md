# crawler/sources/xiaohongshu

小红书采集插头。搜索打开 `search_result`，详情打开 `explore/{note_id}`，都从 `__INITIAL_STATE__` 抽 Vue 状态。

调用方：`tools/search.py`、`tools/product.py`（经 `crawler.registry`）。

## 本目录文件

### `crawler.py`

`XiaohongshuCrawler(BrowserCrawler)`：

- `search` — `goto` `https://www.xiaohongshu.com/search_result`，等 `search.feeds`，`evaluate(SEARCH_JS)`，`items_from_feeds`
- `detail` — `goto` `https://www.xiaohongshu.com/explore/{id}`（可选 `xsec_token`），等 `note.noteDetailMap`，`item_from_detail`

Cookie 域名 `.xiaohongshu.com`。验证码 / 跳登录页抛 `AppError`（`channel.risk` / `account.session_expired`）。

### `extractor.py`

页面脚本常量 + Python 解析：

- `SEARCH_JS` / `SEARCH_READY_JS` — 搜索 feeds
- `DETAIL_JS` / `DETAIL_READY_JS` — 笔记详情 map
- `items_from_feeds` / `item_from_detail` → `CrawlItem`

选择器与 `__INITIAL_STATE__` 路径只允许出现在本文件。

### `__init__.py`

导出 `XiaohongshuCrawler`。

## 子目录

无。扫码：[../../../channels/xiaohongshu/README.md](../../../channels/xiaohongshu/README.md)。开页：[../../../browser/README.md](../../../browser/README.md)。
