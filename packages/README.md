# packages

前端 pnpm 工作区。工作区根清单在仓库根 [`pnpm-workspace.yaml`](../pnpm-workspace.yaml)，
成员 = `packages/*` + `packages/*/*` + `apps/*`。

**一个包 = 一个业务域，或一层机制。** 名字必须能回答「这是干什么的」——
禁止 `packages/ui`、`packages/shared`、`packages/utils` 这类大杂烩命名。

```text
apps/web ──────────────┐
                       ↓
ui-home / ui-ai / ui-composer / ui-account / ui-agent / ui-crawler
                       ↓
ui-layout / ui-feedback ──→ ui-primitives ──→ ui-theme
                       ↓
        runtime · routes · contracts
```

依赖单向：应用 → 业务域 → 骨架 → 底座 → 令牌/协议。任何一层都不反向依赖上层。

## 成员包

| 包 | 职责 | 定位它 |
|----|------|--------|
| [contracts/](contracts/README.md) | 与 Python 的线协议类型（纯类型） | `server/` 改字段时同步 |
| [client/routes/](client/routes/README.md) | 路由契约：路径常量与解析 | 加页面时改 `paths.ts` |
| [client/runtime/](client/runtime/README.md) | HTTP 传输、能力开关、启动预载、错误上报 | 连不上 Server / 判断是否桌面端 |
| [client/ui-theme/](client/ui-theme/README.md) | 设计令牌与全局样式 | 改颜色、圆角、字体 |
| [client/ui-primitives/](client/ui-primitives/README.md) | 无业务的原子组件 + `cn()` | 按钮/输入框长什么样 |
| [client/ui-layout/](client/ui-layout/README.md) | 外壳、标题栏、导航栏、主区域 | 窗口骨架、侧栏 |
| [client/ui-feedback/](client/ui-feedback/README.md) | 错误边界与告警宿主 | 报错怎么展示 |
| [client/ui-ai/](client/ui-ai/README.md) | AI 消息渲染、Markdown、思考过程 | 消息气泡、代码块 |
| [client/ui-composer/](client/ui-composer/README.md) | 输入区、附件、Agent 选择 | 打字框 |
| [client/ui-account/](client/ui-account/README.md) | 账号、扫码登录、登录态告警 | 账号相关 |
| [client/ui-agent/](client/ui-agent/README.md) | 外部 CLI Runtime 探测与运行态 | Agent 探测 |
| [client/ui-crawler/](client/ui-crawler/README.md) | 采集台、结果展示、实时发现 | 采集相关 |
| [client/ui-home/](client/ui-home/README.md) | 首屏、项目条、类型入口 | 首页 |

应用装配层在 [`apps/web/`](../apps/web/README.md)（Vite 根）。

## 工程机制

**源码直出**：每个包的 `exports` 直接指向 `./src/*`，不产出 `lib/`，全仓库仍是单次
Vite 构建。这样既有 pnpm 的真实包边界（依赖显式声明、越界可被发现），又没有多包构建
编排的成本。

```bash
pnpm dev      # → pnpm --filter @v2/app-web dev
pnpm build    # → tsc（全仓库类型检查）+ vite build
```

## 新增一个包

1. 建 `packages/client/ui-<域>/`（`package.json` + `tsconfig.json` + `src/` + `README.md`）
2. `pnpm-workspace.yaml` 已用通配，无需登记
3. **三处必须同时改**，漏一处会在不同阶段炸：
   - 根 `package.json` 的 `dependencies` 加 `"@v2/ui-<域>": "workspace:*"`
   - 根 `tsconfig.json` 的 `paths` 加 `"@v2/ui-<域>"` 与 `"@v2/ui-<域>/*"` 两条
   - 跑一次 `pnpm install` 让 pnpm 建软链
4. 在本文件「成员包」表加一行

## 改结构时的坑

1. **`pnpm-workspace.yaml` 不能写 `packages*`**（会匹配到 `packages-rs`，把 Rust 包当 JS 包扫）。
2. **`@v2/*` 不要加 Vite alias。** 必须走 pnpm 软链解析；加了别名会掩盖「工作区是否真接通」。
3. **Tailwind v4 要显式 `@source`。** 扫描范围写在 `ui-theme/src/index.css`，新增一级包目录
   要回去补一行 —— 漏了不报错，只会悄悄不生成那些类。
4. **不要用 `fs.rmSync(recursive)` 清理 `node_modules/@v2/*` 链接** —— 会穿过 junction
   删掉包的真实内容。只用 `fs.unlinkSync`。
