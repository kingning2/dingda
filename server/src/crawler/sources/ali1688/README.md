# crawler/sources/ali1688

1688 **官方找货** Source（`ApiCrawler`）。经 `channels/ali1688` 调 `find.product`，**不经 Browser**。

## 本目录文件

| 文件 | 职责 |
|------|------|
| `crawler.py` | `Ali1688Crawler`：text / image / link 搜品 |
| `extractor.py` | API 条目 → `CrawlItem` |
| `image.py` | 本地图预处理 → JPEG / base64 路径 |
| `link.py` | 商品链接解析 + 主图抽取 |
| `compare.py` | 同款比价选品（销量/价格/严选） |
| `__init__.py` | 包标记 |

登记在 [`../../registry.py`](../../registry.py) 的 `_API_SOURCES`。

## meta 约定（search）

| key | 说明 |
|-----|------|
| `mode` | `text` / `image` / `link` |
| `image` | 图片路径或 URL（image 模式） |
| `url` | 商品链接（link 模式） |
| `limit` / `sort_type` / `score_level` / `purchase_amount` / `tags` / `ic_tags` | 筛选项 |
