# crawler/sources/xiaohongshu

小红书采集插头。搜索打开 `search_result`，**优先截获**站点签名 XHR
`search/notes`（现网多已不再注入 `__INITIAL_STATE__`），失败再回退 DOM / 页内状态。
详情是**搜索页上的弹层卡片**（不是独立页）：必须带搜索下发的 `xsec_token`
（`xsec_source=pc_search`），否则会 `error_code=300031`；抽取优先 `feed` XHR，再弹层 DOM。
详情打开 `explore/{note_id}?xsec_token=...`。

调用方：`tools/search.py`、`tools/product.py`（经 `crawler.registry`）。

## 本目录文件

### `crawler.py`

`XiaohongshuCrawler(BrowserCrawler)`：

- `search` — `goto` `search_result`，截获 `search/notes` → DOM → `__INITIAL_STATE__`
- `detail` — `goto` `explore/{id}?xsec_token&xsec_source=pc_search`，截获 `feed` / 弹层 DOM

Cookie 域名 `.xiaohongshu.com`。验证码 / 跳登录页 / 300031 抛 `AppError`。

### `extractor.py`

页面脚本常量 + Python 解析：

- `SEARCH_JS` / `DOM_SEARCH_JS` / `PAGE_HINT_JS` — 搜索 feeds / DOM / 诊断
- `DOM_DETAIL_JS` / `DETAIL_HINT_JS` — 详情弹层卡片
- `DETAIL_JS` / `DETAIL_READY_JS` — 旧 noteDetailMap（兜底）
- `items_from_feeds` / `item_from_detail` → `CrawlItem`

选择器与 `__INITIAL_STATE__` 路径只允许出现在本文件。

### `__init__.py`

导出 `XiaohongshuCrawler`。

## 子目录

无。扫码：[../../../channels/xiaohongshu/README.md](../../../channels/xiaohongshu/README.md)。开页：[../../../browser/README.md](../../../browser/README.md)。
