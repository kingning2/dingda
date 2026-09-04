# crawler/sources

每个子目录一个平台 id（与 `create_crawler("xianyu")` 字符串一致）。不要改 `crawler/core` 塞平台 if。

## 本目录文件

### `__init__.py`

包标记。登记平台在 [../registry.py](../registry.py)，不在本文件。

## 子目录

- [xianyu/](xianyu/README.md) — 闲鱼搜索 DOM + 详情 mtop/页内 fallback
- [xiaohongshu/](xiaohongshu/README.md) — 小红书搜索 / 笔记详情（`__INITIAL_STATE__`）
