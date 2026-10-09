# crawler/

`/v1/crawler`：手动搜品与单品详情。

- `search.py` — `POST /search` 一次性搜品，返回列表 + 搜索页 URL
- `search_live.py` — `POST /search/live` SSE：`frame` / `result` / `error` / `done`
- `product.py` — `POST /product` 单品详情（闲鱼：价格、想要人数、留言、`sold_state`）
- `product_live.py` — `POST /product/live` SSE 同上

设计说明：
- `_dto.py` 是前端可直接渲染的商品 DTO + `SearchOutput`/`ProductOutput` → HTTP 映射
- 实现在 [tools 包](../../../../../tools/src/tools/README.md) 与
  [crawler 包](../../../../../crawler/src/crawler/README.md)，不要从这里 import Playwright
