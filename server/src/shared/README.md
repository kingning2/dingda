# shared

跨层稳定类型。平台选择器、mtop 不要进这里。

## 本目录文件

### `errors.py`

`AppError(code, message, status_code)`。工厂：

- `session_expired_error(platform)` → `account.session_expired` 401
- `risk_control_error` → `channel.risk` 403
- `sign_error` → `channel.sign_failed`
- `not_found_error`

FastAPI 在 `core/exceptions.py` 映射 JSON。Channel/Crawler/Tool 统一抛这个，不要裸 `Exception` 当业务失败。

### `__init__.py`

包标记。

## 子目录

无。
