# python

桌面壳里的 **Python Server 子进程**（bundled `uv` + 国内镜像；开发态回退系统 `uv`）。

`lib.rs` setup 里解析 `resources/runtime`、解压平台 Camoufox zip、再 `PythonLifecycle::start_background`。

**打包在 GitHub Actions**（`.github/workflows/desktop-release.yml`），不依赖本机：`prepare-desktop-runtime.mjs` 按 runner OS/arch 从 `daijro/camoufox` Releases 拉对应 zip。

## 本目录文件

### `mod.rs`

导出 `PythonConfig`、`PythonLifecycle`。

### `lifecycle.rs`

- `PythonConfig` — host/port、`server_dir`、`uv_bin`、`extra_env`（国内镜像 / `DINGDA_*`）
- `start_background` — `uv sync --frozen` → spawn → 轮询 `/health` → emit `server-ready` / `server-error`
- 打包态 `startup_timeout` 可到 600s（首次拉依赖）
- `stop` — 杀进程树

## 相关

- [`../paths.rs`](../paths.rs) — server 工作副本、uv、镜像 env
- [`../camoufox.rs`](../camoufox.rs) — 按平台选 zip，用 `zip` crate 解压
