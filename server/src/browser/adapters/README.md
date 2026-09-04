# browser/adapters

浏览器插头。新浏览器：本目录加文件 + `browser/registry.py` 登记。  
页操作共用 [`../page.py`](../page.py) 的 `PlaywrightPage`。产品默认只开 Camoufox，不必再装 Chromium。

## 本目录文件

### `camoufox.py`

`CamoufoxAdapter(BrowserPort)`。默认采集/扫码引擎。指纹 OS 来自 `LaunchOptions`/profile，无商品逻辑。

### `__init__.py`

包标记。

## 子目录

无。插座：[../README.md](../README.md)。
