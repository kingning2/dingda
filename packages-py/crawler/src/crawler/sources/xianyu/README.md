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

### `DOM_PROBE.md`

详情 DOM 探测方法与实测结构（如何拿到选择器）。

### `crawler.py`

`XianyuCrawler`：开页直播 + 套用 `extract.json`。

### `extractor.py`

脚本骨架 + 标准化；不写死平台选择器/字段。

### `__init__.py`

包标记。

## 子目录

无。扫码/签名：[../../../channels/xianyu/README.md](../../../../../channels/src/channels/xianyu/README.md)。
