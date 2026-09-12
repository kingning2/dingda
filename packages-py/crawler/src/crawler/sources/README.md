# crawler/sources

每个子目录一个平台 id（与 `create_crawler("xianyu")` 字符串一致）。不要改 `crawler/core` 塞平台 if。

## 本目录文件

### `__init__.py`

包标记。登记平台在 [../registry.py](../registry.py)，不在本文件。

## 子目录

- [xianyu/](xianyu/README.md) — 闲鱼：列表 mtop+DOM（`extract.json`）/ 详情 mtop
- [xiaohongshu/](xiaohongshu/README.md) — 小红书：列表 XHR+DOM（`extract.json`）/ 笔记详情
- [ali1688/](ali1688/README.md) — 1688 官方找货 API（文本/以图/链接/比价，无 Browser）
