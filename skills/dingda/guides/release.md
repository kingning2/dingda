# Release Guide

骨架阶段无正式发布流程；本文档定义未来发布约束。

## 版本策略

- 桌面应用：SemVer（`apps/desktop/package.json`）
- Rust workspace：统一 `workspace.package.version`

## 发布前检查

```bash
pnpm lint
python skills/dingda/scripts/check_architecture.py
python skills/dingda/scripts/check_contracts.py
pnpm build
```

## Breaking Change 发布

1. Contract v2 + MIGRATION.md
2. 受影响端实现同步迁移（默认 Rust / React；涉及 sidecar 才改 Python）
3. 桌面应用 major 版本 bump
4. 发布说明列出不兼容项

## 产物

| 产物 | 命令 |
|------|------|
| 桌面安装包 | `pnpm tauri build`（自动执行 `build:bundle`：冻结 sidecar + 前端构建） |
| 仅冻结 sidecar | `pnpm build:sidecar` 或 `node tooling/scripts/build-sidecar.mjs --target <triple>` |
| Contract 文档 | 自 `contracts/openapi` 生成 |

`pnpm tauri build` 前会将 PyInstaller 产物复制到 `apps/desktop/src-tauri/binaries/sidecar-<target-triple>[.exe]`，由 Tauri `externalBin` 打入安装包。开发模式 `pnpm tauri dev` 仍使用 `uv` / 源码 sidecar。

## 分支策略

- `main` — 集成分支
- `frontend/<slug>` · `python/<slug>` · `contract/<slug>` — 任务分支（`pnpm branch:create <role> <slug>`）
- `role/<role>` — 长期角色分支（legacy）
- Feature 完成后 PR 回 `main`；切换分支后运行 `pnpm branch:sync`

## 相关

- [review.md](review.md)
- [contracts.md](contracts.md)
