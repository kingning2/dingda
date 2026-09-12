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

### `service.py`

`CrawlerService`：**骨架**。将来给 `api/crawler` 做任务创建/查询。真正搜品现在走 Tool `search`/`product`/`compare`。

### `__init__.py`

包标记。

## 子目录

- [core/](core/README.md) — `BrowserCrawler` / `ApiCrawler` 与 `CrawlItem`
- [sources/](sources/README.md) — 各平台插头
