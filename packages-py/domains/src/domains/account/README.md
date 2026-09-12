# domains/account

产品账号：落库、列表给前端、登录后补昵称头像、闲�?cookie 定时探活�?
不自己签 mtop；探活用 `channels.xianyu.refresh`�?
## 本目录文�?
### `service.py`

`AccountService`：`list` / `patch` / `connect` / `disconnect` / `delete` / `profile_page`。`connect` 目前仅闲鱼：�?connected。点卡片�?`profile_page`（扫码时存下的名称头像）。由 `api/account.py` 调用�?
### `session.py`

`build_session_views(platform, auth_valid, connected)` �?前端徽章文案（已连接/未连�?已过期）和可点的按钮（connect/disconnect/rescan）。纯展示，不�?DB�?
### `persist.py`

`save_login_credentials(...)`：扫码成功时 upsert 账号行（含当时取到的昵称头像）。由 `domains.channel.qr_service` 调用，不要从 Channel 直接�?SQLite�?
### `enrich.py`

`fetch_profile` �?闲鱼 `refresh.profile`。闲�?小红书头像昵称都在扫码成功时写入，登录后不再 enrich。`enrich_account_profile` 仍可手动把昵�?头像写回 accounts 表。失败只打日志�?
### `token_scheduler.py`

`schedule_xianyu_token_scheduler`：warmup 时挂上。闲鱼启动探活走 `token()`（先 `loginuser.get`，失败再浏览器静默续期，续不上才标过期）；再探活小红书 / 1688；之后每 10 分钟周期续期。

### `__init__.py`

包标记�?
## 子目�?
无。表结构：[../../infrastructure/db/README.md](../../../../infrastructure/src/infrastructure/db/README.md)�?