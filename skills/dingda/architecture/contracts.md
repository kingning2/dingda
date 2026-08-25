# Contracts

`contracts/` 是 DingDa 跨端共享的**唯一真相源**。默认实现端是 Rust 与 React；Python 仅 sidecar 例外时才更新。

## 目录结构

```
contracts/
├── README.md
├── CHANGELOG.md
├── schema/v1/              # JSON Schema（DTO / Event / Error）
│   └── <feature>/
│       ├── dto/
│       ├── ipc/
│       ├── event/
│       └── error/
├── openapi/                # HTTP / sidecar API
│   └── sidecar.v1.yaml
├── codegen/                # 生成脚本与配置
└── compatibility/
    ├── FIELD_RULES.md
    └── MIGRATION.md
```

## 变更流程

```
┌─────────────┐
│ 1. Contract │  修改 schema 或 openapi
└──────┬──────┘
       ▼
┌─────────────┐
│ 2. Codegen  │  sync_contracts.py / codegen 脚本
└──────┬──────┘
       ▼
┌─────────────┐
│ 3. 实现端   │  默认 Rust → React
│             │  仅 sidecar 例外才改 Python
└─────────────┘
```

**禁止**跳过步骤 1 直接改实现。

## Schema 版本策略

| 变更类型 | 做法 |
|----------|------|
| 新增可选字段 | 同版本，更新 CHANGELOG |
| 新增必填字段 | 评估兼容性；可能需 v2 |
| 删除/重命名字段 | 新 `schema/v2` + MIGRATION.md |
| IPC 命令签名变更 | Breaking — 须评审 |

## Codegen 输出

| 目标 | 路径 |
|------|------|
| TypeScript | `packages/contracts/src/` |
| Rust | `apps/desktop/src-tauri/src/contracts/contracts/` |
| Python | `python/contracts/` |

## PR 要求

- Contract PR 至少 **2 人 Approve**

## 相关文档

- [../guides/contracts.md](../guides/contracts.md)
- [../recipes/add-contract.md](../recipes/add-contract.md)
- [../scripts/sync_contracts.py](../scripts/sync_contracts.py)
