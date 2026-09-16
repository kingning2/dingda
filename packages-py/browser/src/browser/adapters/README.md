# browser/adapters

浏览器插头。新浏览器：本目录加文件 + `browser/registry.py` 登记。  
页操作共用 [`../page.py`](../page.py) 的 `PlaywrightPage`。产品默认只开 Camoufox，不必再装 Chromium。

> 2026-09-15 实测记录（别再重做这件事）：给闲鱼加过 Playwright Chromium 插头想换掉
> Camoufox 过滑块，结论是**不可行也没收益**。
> - 自带 Chromium：无头被闲鱼判「非法访问」（搜索页 `links=0`，正文「请使用正常浏览器访问闲鱼」）；
>   有头直接白页 `body.length=0`。
> - 系统 Chrome（`channel="chrome"`）：无头同样「非法访问」，有头才正常（`links=30`），
>   但耗时 15s vs Camoufox 17s，且多依赖用户机器装没装 Chrome。
> - 换言之：过不过得去主要看**有没有 Camoufox 的指纹伪装 + 有头**，不是 Chromium 的 CDP 增量。

## 本目录文件

### `camoufox.py`

`CamoufoxAdapter(BrowserPort)`。启动时通过 [`../camoufox_bin.py`](../camoufox_bin.py) 注入 `executable_path`（安装包平台 zip，禁止 GitHub fetch）。

### `__init__.py`

包标记。

## 子目录

无。插座：[../README.md](../README.md)。
