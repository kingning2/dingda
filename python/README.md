# Python Sidecar（单一项目，无 uv workspace）

DingDa 默认能力在 **Rust**。Python 只在 Rust 生态不够时使用（Playwright / Camoufox），由 Rust 托管生命周期。

```
React → Tauri IPC → Rust → Python Sidecar
```

## 目录

```
python/
├── pyproject.toml
└── src/dingda_sidecar/      # 包根（src 布局）
    ├── main.py              # 进程入口（--ipc 必填）
    ├── runtime/             # 宿主 IPC / lifecycle
    ├── agent/ skills/ tools/
    ├── crawlers/
    ├── services/ common/ config/
    └── contracts/
```

## 开发

```bash
uv sync
uv run python -m dingda_sidecar.main --port 8787
```
