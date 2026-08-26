# Python Sidecar（单一项目，无 uv workspace）

DingDa 默认能力在 **Rust**。Python 只在 Rust 生态不够时使用（Playwright / Camoufox），由 Rust 托管生命周期。

```
React → Tauri IPC → Rust → Python Sidecar
```

## 目录

```
python/
├── pyproject.toml
├── application/sidecar/     # 进程入口 + channel handlers
├── runtime/                 # 宿主 IPC / lifecycle
├── runtimes/                # 子运行时生命周期
├── agent/ skills/ tools/
├── crawlers/
├── contracts/
└── sidecar.spec
```

## 开发

```bash
uv sync
uv run python -m application.sidecar.main --port 8787
```
