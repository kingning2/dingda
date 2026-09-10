# scripts

## `prepare-desktop-runtime.mjs`

给 **GitHub Actions / 任意 CI** 用的跨平台准备脚本（也可用本机 `pnpm prepare:desktop-runtime`）。

产出 `src-tauri/resources/runtime/`：

| 路径 | 说明 |
|------|------|
| `bin/uv(.exe)` | 打进安装包的 uv |
| `server/` | 源码 + `uv.lock` + 国内镜像 `uv.toml` |
| `camoufox/camoufox-{tag}.zip` | 当前平台浏览器包 |

环境变量：

- `GITHUB_TOKEN` — CI 拉 Release 提高限额（Actions 自带）
- `CAMOUFOX_RELEASE_TAG` — 可选钉死 tag（也可用 repo Actions variable）
- `CAMOUFOX_ZIP` — 本地已有 zip 时跳过下载
- `REQUIRE_CAMOUFOX=1` — 缺 zip 则失败（release workflow 已开）
- `SKIP_CAMOUFOX=1` — 仅调试

平台 tag 与 Rust `camoufox_platform_tag()` 一致。
