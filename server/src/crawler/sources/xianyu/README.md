# crawler/sources/xianyu

闲鱼采集插头。搜索必须开 goofish 搜索页（列表不在公开稳定 mtop 上）；详情尽量 HTTP，少开商品页。

调用方：`tools/search.py`、`tools/product.py`（经 `crawler.registry`）。

## 本目录文件

### `crawler.py`

`XianyuCrawler(BrowserCrawler)`：

- `search` — `goto` `https://www.goofish.com/search`，`evaluate(EXTRACT_JS)`，滚动 `SCROLL_JS`，`items_from_payload`
- `detail` — `Session.from_cookie_header` + mtop 详情；失败则开商品页 `evaluate(VIEW_JS)`，`item_from_view`

Cookie 域名 `.goofish.com`。风控/过期抛 `AppError`（`channel.risk` / `account.session_expired`）。

### `extractor.py`

页面脚本常量 + Python 解析：

- `EXTRACT_JS` / `SCROLL_JS` — 搜索卡片
- `VIEW_JS` — 商品页内嵌 mtop
- `items_from_payload` / `item_from_view` / `item_from_mtop_detail` → `CrawlItem`
- `item_id_from_url`

选择器只允许出现在本文件，不要渗进 `browser/`。

### `__init__.py`

包标记。

## 子目录

无。扫码/签名：[../../../channels/xianyu/README.md](../../../channels/xianyu/README.md)。开页：[../../../browser/README.md](../../../browser/README.md)。
