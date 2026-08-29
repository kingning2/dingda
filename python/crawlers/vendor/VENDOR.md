# Vendored 第三方爬虫来源

| 目录 | 上游仓库 | 锁定 SHA | 许可证 | 说明 |
|---|---|---|---|---|
| `xhs_cli/` | https://github.com/jackwener/xhs-cli | `3ce7141` | Apache-2.0（LICENSE 随目录保留） | Camoufox 浏览器客户端（导航真实页面读 `__INITIAL_STATE__`；小红书搜索回退通道用 `XhsClient`） |
| `goofish_cli/` | https://github.com/fancyboi999/goofish-cli | `771382c` | Apache-2.0（LICENSE + NOTICE 随目录保留） | 闲鱼 DOM 提取与 Cookie 兜底 |
| `xiaohongshu_mcp/` | https://github.com/xpzouying/xiaohongshu-mcp | `6fb866a` | Apache-2.0（LICENSE 随目录保留） | 小红书 Go sidecar（编译为二进制，REST API） |

## vendored 时相对上游的改动

- 删除 CLI / MCP 入口：`xhs_cli/cli.py`、`goofish_cli/cli.py`、`goofish_cli/mcp_server.py`
- `goofish_cli` 全部绝对导入 `goofish_cli.*` → `crawlers.vendor.goofish_cli.*`（`xhs_cli` 为相对导入，无需改写）
- `xhs_cli` 为 Camoufox 浏览器客户端，无需 API 签名/代理配置；上游声明的 `camoufox[geoip]` 的
  geoip extra 未用到（代码不涉及定位），`click` 随 `cli.py` 删除而不再需要
- `xhs_cli/client.py`（仅此一处代码改动，透传式，升级易重放）：`XhsClient.__init__` 增加
  可选参数 `headless` / `executable_path` / `ff_version`；`start()` 将其透传给 `Camoufox(...)`。
  系统 Camoufox 定位与 ff_version 推断在应用侧（`crawlers/core/camoufox.py::resolve_camoufox_executable_with_version`）
- `xiaohongshu_mcp`：仅保留 Go 源码与构建所需（`browser/ configs/ cookies/ errors/ humanize/ pkg/ xiaohongshu/` + 根 `*.go`），
  删除 `cmd/login`（独立登录工具，服务端经 `/api/v1/login/qrcode` 完成登录）、`*_test.go` 与
  `assets/ docs/ examples/ deploy/ docker/ donate/ skills/` 等非源码/部署目录；
  内置浏览器**下载已迁至 Rust 插件系统**（插件 id `xhs-mcp-browser`，见 `apps/desktop/src-tauri/src/config/plugins/xhs_mcp_browser.rs`），
  Go 侧 `browser/browser_download.go` 仅保留路径解析（`DINGDA_PLUGINS_DIR/xhs-mcp-browser/` 下找 `chrome.exe`），不再下载；
  编译见 `tooling/build/build_xhs_mcp.sh`，产物 `bin/xiaohongshu-mcp[.exe]`（gitignore）
- 依赖面收窄：不再需要 `typer` / `mcp`（随删除的入口）；其余 Python 依赖见 `python/pyproject.toml`

## 适配方式

- **闲鱼（goofish）搜索**在 `crawlers/goofish/search.py`：浏览器用**系统 Camoufox 会话**
  （`browser_page_session`，Firefox 指纹 + TLS），复用 `goofish_cli` 的搜索页 DOM 提取
  （`_EXTRACT_JS` / `_build_search_url` / `auto_scroll`）。Cookie 由 DingDa 账号库注入；
  为空时回退 `goofish_cli` Session 三级兜底（cookies.json → 本机浏览器 → 报错）。
- **小红书搜索**在 `crawlers/xiaohongshu/search.py`（双通道）：
  - 优先：`xiaohongshu_mcp` REST API（`POST /api/v1/feeds/search`），登录态由 mcp 自带 QR 管理
  - 回退：vendored `XhsClient.search_notes`（复用系统 Camoufox，Cookie 由账号库注入）
- 无头策略统一走系统约定（`DINGDA_XIANYU_SEARCH_HEADLESS` / `-headless` flag）。

## 升级方式

每个目录都可「整目录覆盖 + 重放下列改动」，**不要手工改 vendored 源码**。

### `xhs_cli/`（Python）
```bash
git clone --depth 1 https://github.com/jackwener/xhs-cli.git /tmp/xhs-cli
rm -rf python/crawlers/vendor/xhs_cli
cp -r /tmp/xhs-cli/xhs_cli python/crawlers/vendor/xhs_cli   # 只拷包内源码
cp /tmp/xhs-cli/LICENSE python/crawlers/vendor/xhs_cli/
rm python/crawlers/vendor/xhs_cli/cli.py                    # 删 CLI 入口
# 重放：给 client.py 的 __init__ 加 headless/executable_path/ff_version 透传（见上文「改动」）
# 更新本表 SHA
```

### `goofish_cli/`（Python）
```bash
git clone --depth 1 https://github.com/fancyboi999/goofish-cli.git /tmp/goofish-cli
rm -rf python/crawlers/vendor/goofish_cli
cp -r /tmp/goofish-cli/goofish_cli python/crawlers/vendor/goofish_cli
cp /tmp/goofish-cli/LICENSE /tmp/goofish-cli/NOTICE python/crawlers/vendor/goofish_cli/ 2>/dev/null
rm python/crawlers/vendor/goofish_cli/cli.py python/crawlers/vendor/goofish_cli/mcp_server.py
# 重放：绝对导入改写（唯一一处批量改动）
sed -i 's/^from goofish_cli/from crawlers.vendor.goofish_cli/; s/^import goofish_cli/import crawlers.vendor.goofish_cli/' \
  $(find python/crawlers/vendor/goofish_cli -name '*.py' | grep -v __pycache__)
# 更新本表 SHA
```

### `xiaohongshu_mcp/`（Go）
```bash
git clone --depth 1 https://github.com/xpzouying/xiaohongshu-mcp.git /tmp/xhs-mcp
# 覆盖 browser/ cmd/ configs/ cookies/ errors/ humanize/ pkg/ xiaohongshu/ + 根 *.go + go.mod/sum/LICENSE
# 删 *_test.go 与非源码目录（assets/docs/examples/deploy/docker/donate/skills）
# 重放：browser_download.go 改为仅路径解析（ResolveBrowser，不下载）；browser.go/main.go 改调它
# 若浏览器版本更新：同步 apps/desktop/src-tauri/src/config/plugins/xhs_mcp_browser.rs 的 URL
# 重编译：bash tooling/build/build_xhs_mcp.sh；更新本表 SHA
```
