# channels/xianyu

闲鱼账号侧全部实现。搜品列表 DOM 在 crawler；这里负责登录态、签名 HTTP、IM、自己的商品 CRUD。

调用关系（简化）：

```text
扫码: channel.py → login.py + renew.py + browser.sync；过滑块 → slider.py
mtop: session.py + sign.py → mtop.py
IM:   token.py → ws.py → message.py
发品: media.py + category.py + location.py → item.py
续期: refresh.py（HTTP ping / 快速进入）; renew.py（滑块/有头）
写保护: limiter.py + guard.py 包住 delete/publish/send/upload
风控: risk.py（判定）+ slider.py（自动过滑块）
```

## 本目录文件

### `channel.py`

`XianyuQrChannel`：后台线程跑扫码状态机。出码、检测已扫、成功后调一次 `user.page.nav` 写昵称头像、超时或 punish 页则 `renew()`。给 `domains.channel` / `api.channel` 轮询。

### `login.py`

扫码页原语（同步 Playwright page，由 `open_login_page()` 打开 goofish 登录）：

- `capture_qr` — 从 passport iframe 抠二维码
- `has_scanned_cookies` / `has_all_login_cookies` / `has_login_completed` — 进度判断
- `find_passport_frame` / `wait_for_qr_frame`

不负责启动 BrowserManager；开页上下文由 Channel 组装。

### `cookies.py`

闲鱼 Cookie 注入规则：`_m_h5_tk` 等走 `.taobao.com`，其余 `.goofish.com`。`to_browser_cookies` 给 BrowserPort；`cookie_map` 从 page cookies 收成 dict。**不要**把这套域名写进 browser adapter。

### `sign.py`

execjs 加载 `static/goofish_js_version_2.js`。`generate_sign(t, token, data)`、`generate_device_id`、`generate_mid`、`generate_uuid`、`decrypt`。mtop 和 WS 编解码依赖它。

### `session.py`

`Session.from_cookie_header(cookie)`：解析出 `unb`、`_m_h5_tk`，建 `requests.Session`，按 unb 缓存 `device_id`（`~/.dingda/v2/xianyu/device.json`）。`h5_token` 给签名用。不写 `~/.goofish-cli`。

### `mtop.py`

`call(session, api, data, ...)`：拼 h5api URL、签名、POST。按 `ret` 映射 `AppError`（风控 / 登录过期 / 签名错 / 404）。可恢复的 token 失效会调 `refresh.refresh` 后续一次。闲鱼几乎所有 HTTP 业务都进这里。

### `token.py`

IM 用的 `accessToken`：`mtop.taobao.idlemessage.pc.login.token`。按 unb 缓存，避免狂打该风控敏感接口。`get_access_token`、`refresh_login`（loginuser ping）。WS `/reg` 前必须有 token。

### `refresh.py`

登录态续命（不弹滑块窗口的那条）：

- `refresh(cookies)` — 无头打开首页，点「快速进入」
- `probe` / `status` — HTTP 探活
- `profile` — 扫码成功时调一次 `mtop.idle.web.user.page.nav`，抽出 `module.base` 昵称头像后落库
- `token` — ping 失败再走浏览器续 cookie

账号定时任务、Tool `status` 走这里。

### `renew.py`

扫码失败或 punish 页：Camoufox 无头自动滑块，不行再有头让人滑。`renew(...)` 返回 `(ok, detail, cookies)`。`channel.py` 在风控分支调用。

### `risk.py`

`is_risk_control_text`、`page_is_punish(url)`、`RiskControlError`。只判断，不解题。

### `slider.py`

闲鱼 Baxia / NoCaptcha 自动过滑块：`try_solve_slider`、`clear_risk_cookies`、`auto_slider_enabled`。
`renew.py` 与 `crawler/sources/xianyu` 在 punish / 验证码时调用。不属于 Browser 层。

### `ws.py`

闲鱼 IM WebSocket（`wss-goofish.dingtalk.com`，LWP JSON）：

- `connect` / `register` / `heartbeat_loop` / `build_ack`
- `send_text` / `send_image` / `create_chat`
- `list_user_messages`、`collect_session_cids`、`collect_events`
- 推送解码：`extract_push_messages`、`extract_incoming_text`、`extract_meta_event`
- `run_forever` — 常驻重连（产品侧；MCP `watch` 用短时 `collect_events`）

### `message.py`

给 Tool 的 IM 门面（cookie 字符串进，内部建 Session）：

- `chats` — mtop session.sync，可选短时 WS 补 cid
- `history` — WS 拉历史
- `send` — 发文本/图（带 limiter+guard）
- `watch` — 短时收下行事件

### `item.py`

自己的商品：`items`（翻页 list）、`delete`、`publish`（内部串联 upload → category → location → mtop publish）。写操作包 `acquire`+`hold`。

### `media.py`

`upload(cookie, path)`：multipart 到 `stream-upload.goofish.com`，返回 url/宽高。发品和发图消息的前置。

### `category.py`

`recommend(cookie, title, images)`：AI 类目 `mtop.taobao.idle.kgraph.property.recommend`，给 publish 填 `itemCatDTO`。

### `location.py`

`default(cookie, lon, lat)`：默认发布 POI `mtop.taobao.idle.local.poi.get`。

### `limiter.py`

写操作令牌桶。`acquire("item.write"|"message.write")`。状态 `~/.dingda/v2/xianyu/limiter.json`。超限 `channel.rate_limited`。`DINGDA_WRITE_RPM` 可调。

### `guard.py`

风控熔断。`hold()` 包住写；抓到 `channel.risk` 就 `trip()`。冷却期内直接拒绝。`reset()` 给 Tool `reset`。状态 `circuit.json`。

### `__init__.py`

包标记。

### `static/goofish_js_version_2.js`

签名 JS 原文，仅 `sign.py` 读取。不要在 crawler 里再引一份。

## 子目录

无。闲鱼**搜索页 DOM** 在 [../../crawler/sources/xianyu/README.md](../../crawler/sources/xianyu/README.md)。
