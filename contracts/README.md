# DingDa Contracts

三端共享契约层 — **唯一真相源**（DTO · IPC · HTTP · Event · Error）。

## 变更流程（禁止跳过）

```
1. 修改 Contract（本目录）
       ↓
2. Code Generation（pnpm contracts:sync）
       ↓
3. 受影响实现端：默认 Rust → React
   仅当该能力必须走 sidecar 时才改 Python
```

**禁止**先改实现再补契约。临时原型须在 PR 标注并尽快补全。

## 目录

- `schema/v1/` — JSON Schema
- `openapi/` — OpenAPI 规范（含 sidecar 管理面 `sidecar.v1.yaml` 与 `sidecar.paths/`）

## 变更工作流

1. 编辑 schema / openapi
2. 运行 `pnpm contracts:sync`（或 `python tooling/dingda/scripts/sync_contracts.py`）
3. 更新受影响端引用（默认 Rust / TS；仅 sidecar 例外才改 Python）
4. PR 至少 2 人 Approve

## 相关文档

- [`docs/managed/architecture/README.md`](../docs/managed/architecture/README.md) — 系统架构
- [`.cursor/rules/master.md`](../.cursor/rules/master.md) — 全局架构约束
