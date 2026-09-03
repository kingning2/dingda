# Vendored 第三方工具

本目录存放**上游仓库整包**（检出锁定版本，不含 `.git`）。业务代码只依赖 `src/adapters/` 的稳定接口。

| 目录 | 上游仓库 | 锁定版本 | 许可证 | Python 路径 |
|------|----------|----------|--------|-------------|
| `xhs_cli/` | https://github.com/jackwener/xhs-cli | 见 `vendor.lock.yaml` | Apache-2.0 | 仓库根 |
| `goofish_cli/` | https://github.com/fancyboi999/goofish-cli | 见 `vendor.lock.yaml` | Apache-2.0 | `src/` |

## 同步（按锁文件，不会自动跟 main 最新）

在 `backend` 下执行，按 `vendor.lock.yaml` 中的 commit 检出：

```bash
uv run python tooling/sync_vendor.py xhs_cli
uv run python tooling/sync_vendor.py goofish_cli
uv run python tooling/sync_vendor.py --all
```

## 升级上游（显式操作）

需要跟踪 `manifest.yaml` 里 `upstream.ref`（默认 `main`）最新代码时：

```bash
uv run python tooling/sync_vendor.py --update xhs_cli
uv run python tooling/sync_vendor.py --update --all
```

会更新 `vendor.lock.yaml` 中的 `rev` 并覆盖 `third_party/<path>/`。

升级后**不需要**改 `src/domains`、`src/api` 等业务代码。

## 边界

- **禁止**在 `domains/`、`api/` 中 `import xhs_cli` / `import goofish_cli`
- **必须**通过 `src.adapters.crawler` 或 `src.adapters.registry.import_vendor()`
