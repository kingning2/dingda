# channels

**账号 / 登录 / 平台 HTTP API 语义**。扫码、cookie、闲鱼 mtop 签名、IM。  
不是搜品 Source（那是 crawler）；浏览器引擎实现也不在这里（那是 browser）。

业务要「按平台开扫码」：`registry.create_qr_login_channel("xianyu")`，不要 `if platform ==`。

## 本目录文件

### `base.py`

抽象类 `QrLoginChannel`：`start_login` 返回 runtime，`snapshot(runtime)` 返回 `LoginSnapshot`。新平台 Channel 必须实现这两个方法。

### `types.py`

`LoginSnapshot` / 登录状态枚举（排队、出码、已扫、成功、失败）。HTTP 和前端轮询都认这个形状。

### `registry.py`

`{"xianyu": XianyuQrChannel, "xiaohongshu": XiaohongshuQrChannel}`。`create_qr_login_channel(platform)` 找不到就 `AppError("channel.qr_unsupported")`。

### `cookie_header.py`

`parse_cookie_header("a=1; b=2")` → dict；`cookie_header(dict)` → 字符串。mtop Session、token 刷新、Tool 入参 cookie 都用它。

### `profile_fields.py`

从闲鱼/小红书资料 JSON 树里抽昵称、头像。小红书登录完成时会用；闲鱼登录走 `refresh.profile`。

### `qr_terminal.py`

把二维码 PNG/base64 打到终端（开发扫码）。Channel 出码后可选调用。产品 UI 不走这里。

### `__init__.py`

包标记。

## 子目录

- [xianyu/](xianyu/README.md) — 闲鱼：扫码、mtop、IM、发品、限流熔断（文件最多，逐个说明）
- [xiaohongshu/](xiaohongshu/README.md) — 小红书扫码页与 Channel
