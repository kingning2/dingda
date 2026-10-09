# lib/

被多个路由端点、启动钩子复用的模块。当前只有：

- `watch_feed.py` — 商品监控**取数插头**：用 `tools.product` 实现
  `domains.watch.base.ProductFetcher` 插座。

`domains` 不依赖 `tools`，而本层是唯一同时依赖两者的地方，所以插头放这里。
必须传 `allow_login_recovery=False`——后台轮询不能弹扫码窗，会话过期就让这次轮询失败、
由 token 调度器去静默续期。
