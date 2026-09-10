# browser/adapters

浏览器插头。新浏览器：本目录加文件 + `browser/registry.py` 登记。  
页操作共用 [`../page.py`](../page.py) 的 `PlaywrightPage`。产品默认只开 Camoufox，不必再装 Chromium。

## 本目录文件

### `camoufox.py`

`CamoufoxAdapter(BrowserPort)`。启动时通过 [`../camoufox_bin.py`](../camoufox_bin.py) 注入 `executable_path`（安装包平台 zip，禁止 GitHub fetch）。

### `__init__.py`

包标记。

## 子目录

无。插座：[../README.md](../README.md)。
