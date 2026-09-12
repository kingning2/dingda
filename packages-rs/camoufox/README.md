# camoufox

Camoufox 浏览器运行时的**定位与解压**。只负责把 exe 找出来，不启动浏览器。

壳把结果注入 `DINGDA_CAMOUFOX_EXE` 给 Python 侧（见 [../python/README.md](../python/README.md)）。

## 本目录文件

### `camoufox.rs`

- `camoufox_platform_tag()` — 按 `std::env::consts::{OS,ARCH}` 映射官方 tag（`win.x86_64` 等）
- `bundled_camoufox_zip(app)` — 找 `resources/runtime/camoufox/camoufox-{tag}.zip`
- `extract_camoufox_zip(zip, dest)` — 用 **`zip` crate** 逐文件解压，中断时不写 stamp
- `ensure_camoufox_exe(app)` — 就绪则直接返回；否则解压到 `~/.dingda/v2/camoufox/current`
- `find_camoufox_exe(root)` — 在目录树里找启动器（含 macOS `.app` 布局）

**就绪条件**：exe + `properties.json` + `.extract-stamp` 与 zip 的 size/mtime 对齐。
三者齐备才算可用，避免半截解压后误判。

`find_camoufox_exe` 原本在 `common::paths`；它是 Camoufox 专属知识（认识 exe 名与
`.app` 布局），迁入本包后 `common` 不再反向依赖 Camoufox，循环依赖被打断。

### `lib.rs`

模块声明与 re-export：`bundled_camoufox_zip`、`camoufox_platform_tag`、
`ensure_camoufox_exe`、`extract_camoufox_zip`、`find_camoufox_exe`。

## 子目录

无。

## 打包来源

zip 由 GitHub Actions 打包（`.github/workflows/desktop-release.yml`）经
`scripts/prepare-desktop-runtime.mjs` 按 runner OS/arch 从 `daijro/camoufox`
Releases 拉取，不打进 git。
