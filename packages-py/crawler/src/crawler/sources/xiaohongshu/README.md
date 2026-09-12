# crawler/sources/xiaohongshu

小红书采集插头。搜索打开 `search_result`，优先截获 `search/notes`，失败再 DOM / `__INITIAL_STATE__`。
详情优先 `feed` XHR，再弹层 DOM。**平台选择器 / API / 字段一律改 `extract.json`。**

调用方：`tools/search.py`、`tools/product.py`（经 `crawler.registry`）。

## 本目录文件

### `extract.json`（改版只改这里）

- `urls` — 搜索/笔记 URL、cookie 域名
- `list_api` / `detail_api` / `comment_api` — XHR 匹配与字段路径
- `dom` / `detail_dom` / `comments_dom` / `detail_hint_dom` — DOM 选择器
- `signals` / `capture` / `state` — 登录墙、截获提示、INITIAL_STATE 路径

### `crawler.py`

`XiaohongshuCrawler`：开页直播 + 套用 `extract.json`（经 extractor 的 `*_arg` / match helpers）。

### `extractor.py`

脚本骨架 + 标准化；不写死平台选择器/字段。

### `__init__.py`

导出 `XiaohongshuCrawler`。

## 子目录

无。扫码：[../../../channels/xiaohongshu/README.md](../../../../../channels/src/channels/xiaohongshu/README.md)。
