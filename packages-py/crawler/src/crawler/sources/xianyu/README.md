# crawler/sources/xianyu

闲鱼采集插头。搜索开页直播；列表优先 mtop，失败再 DOM。详情优先 mtop HTTP，再页内 `lib.mtop`，再 **DOM（`detail_dom`）**。
**平台选择器 / API / 字段一律改 `extract.json`。**

调用方：`tools/search.py`、`tools/product.py`（经 `crawler.registry`）。

## 本目录文件

### `extract.json`（改版只改这里）

- `urls` — 搜索/商品 URL、cookie 域名
- `list_api` / `detail_api` / `comment_api` — mtop 名与字段路径
- `dom` / `view` / `detail_dom` — 搜索 DOM、页内详情 mtop、详情 DOM 兜底
- `signals` — 登录墙 / 风控 / 空结果文案
- `sold_state` — 商品状态文案 → 售出态的关键词表（sold / delisted / on_sale）

### `DOM_PROBE.md`

详情 DOM 探测方法与实测结构（如何拿到选择器）。

### `crawler.py`

`XianyuCrawler`：开页直播 + 套用 `extract.json`。

### `extractor.py`

脚本骨架 + 标准化；不写死平台选择器/字段。

`sold_state_from_status(status)` 把详情状态文案映射成 `contracts.watch.SoldState`，结果写进
`CrawlItem.raw['sold_state']`，同时原文留在 `raw['status']`。**关键词未命中时返回 `unknown`
并打一条 `sold_state unmatched status=…` 日志——看到这条日志说明真实文案变了，按日志原文补
`extract.json` 的 `sold_state` 小节即可，不用改代码。**

### `__init__.py`

包标记。

## 子目录

无。扫码/签名：[../../../channels/xianyu/README.md](../../../../../channels/src/channels/xianyu/README.md)。
