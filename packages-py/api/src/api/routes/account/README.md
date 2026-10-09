# account/

`/v1/accounts`：账号库读写。登录态由扫码 / 探活侧写入，本域只做读、删与偏好 PATCH。

- `list_accounts.py` — `GET ""` 列表，可按 `platform` 过滤
- `browser_session.py` — `GET /browser-session` 商品预览注入用 cookie + localStorage
- `profile.py` — `GET /{account_id}/profile` 个人主页摘要
- `patch_account.py` — `PATCH /{account_id}` 改展示名、自动连接等偏好
- `connect_account.py` / `disconnect_account.py` — `POST /{account_id}/connect|disconnect`
- `delete_account.py` — `DELETE /{account_id}`

设计说明：
- 前缀 `/v1/accounts` 落在**每个动作文件**里，域 `__init__.py` 只留 tags——
  FastAPI 不允许「子路由空路径 + include 空前缀」两级拼接（list 端点路径为 `""`）
- 服务见 [account 域](../../../../../domains/src/domains/account/README.md)
