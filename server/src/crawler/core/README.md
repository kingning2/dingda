# crawler/core

所有 Source 共用的插座和结果类型。**不要**在这里写闲鱼卡片 CSS、mtop API 名。

## 本目录文件

### `base.py`

- `BrowserSessionOptions` — 代理、指纹、cookies、`cookie_domain`（dict cookie 注入时必填，如 `.goofish.com`）
- `BrowserCrawler` — 打开/关闭带 ContextOptions 的 Page；子类实现 `search`，`detail` 默认未实现可覆盖
- `ApiCrawler` — 无浏览器插座（官方 HTTP 找货等）；子类实现 `search`

开页策略只写一遍：Source 不要自己 `launch` 浏览器。API 平台走 `ApiCrawler`，不 acquire BrowserPort。

### `types.py`

- `CrawlContext` — `task_id`、可选 `account_id`
- `CrawlItem` — 标准化商品（id、标题、价、卖家、链接、raw）
- `CrawlResult` — items + 分页/元数据

Tool 把 `CrawlItem` 映射成 SearchItem/ProductItem。

### `__init__.py`

包标记。

## 子目录

无。闲鱼实现：[../sources/xianyu/README.md](../sources/xianyu/README.md)。
