# channels/xiaohongshu

小红书**扫码登录**与 Cookie 域名。搜品在 `crawler/sources/xiaohongshu/`，没有 IM Tool。

登记在 `channels/registry.py` 的 `"xiaohongshu"`。HTTP 仍走 `POST /v1/channel/qr/start` + `platform=xiaohongshu`。

## 本目录文件

### `channel.py`

`XiaohongshuQrChannel`：后台线程 `_run`。出码、轮询 Edith 扫码状态、成功后导出 cookie/昵称/头像。超时默认 240s（闲鱼 120s，在 `qr_service`）。

### `login.py`

页面与扫码原语：打开 `xiaohongshu.com/login`，拦截 `qrcode/create`、轮询 `qrcode/status` / `qrcode/userinfo`。扫码成功后打开探索页，**截获站点签名 XHR**（`user/me` / `otherinfo`）读昵称头像（现网多数已不再注入 `__INITIAL_STATE__`），再落库。

### `status.py`

`probe(cookie)`：注入 cookie 打开 `/explore`，看侧栏 `.main-container .user .link-wrapper .channel`（对齐 xiaohongshu-mcp `CheckLoginStatus`）。启动预热时写 `auth_valid`。

### `cookies.py`

`to_browser_cookies`：账号 cookie 注入 `.xiaohongshu.com`。给 Crawler / Tool 会话用。

### `risk_recovery.py`

`XiaohongshuRiskRecovery`：爬虫步骤级风控恢复。暂无稳定自动解法，直接开有头窗口阻塞等用户过验证；
判过要求验证 UI 消失 + 正文渲染 + 稳定保持，过完把窗口里的新 Cookie 写回原 page 再让调用方重试。

### `__init__.py`

包标记。

## 子目录

无。插座：[../README.md](../README.md)。采集：[../../crawler/sources/xiaohongshu/README.md](../../crawler/sources/xiaohongshu/README.md)。
