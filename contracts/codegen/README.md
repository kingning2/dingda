# Contract Codegen

将 `contracts/schema/v1/` 中的 JSON Schema 同步为三端类型。

## 运行

```bash
pnpm contracts:sync
# 或
python skills/dingda/scripts/sync_contracts.py
```

`pnpm tauri dev` / `pnpm tauri build` 会在编译前自动执行上述同步（见 `tooling/scripts/sync-contracts.mjs`）。

增量策略：仅 **新增 / 更新 / 删除** 与 schema 差异对应的生成文件；未变化的文件与 index 不会重写。

## 输出

| 端 | 目录 |
|----|------|
| TypeScript | `packages/contracts/src/generated/` |
| Rust | `apps/desktop/src-tauri/src/contracts/contracts/` |
| Python | `python/contracts/generated/` |

变更顺序仍为：**Contract → sync_contracts → 受影响端**（默认 Rust → React；仅 sidecar 例外才改 Python）
