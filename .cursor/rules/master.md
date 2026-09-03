# Master（全局基线）规则

适用范围：**全仓库**（所有分支都必须遵守）。

---

## 当前阶段（Architecture Skeleton）

| 允许 | 禁止 |
|------|------|
| 创建目录、crate、trait、DTO、Contract、Interface、Mock | 实现任何业务逻辑 |
| 骨架、契约、规范、工具链 | 为演示写 Demo |
| | 为方便绕过架构 |

> 未完成架构评审前，**禁止**开始写业务功能。

---

## First Principles（设计原则）

所有设计必须遵守，违反即视为错误：

1. **Contracts First** — 契约是唯一真相源
2. **Feature First** — 按 Feature 垂直切分，互不渗透
3. **Dependency Inward** — 依赖指向内层（UseCase → Ports → Infrastructure）
4. **Event Driven** — 跨模块用 Pub/Sub，禁止直接调用
5. **Local First** — 默认本地运行，数据留在本机
6. **Offline First** — 核心能力可离线工作
7. **Testable by Design** — 通过 Port/Mock 可测
8. **Composition over Inheritance** — 组合优于继承
9. **Explicit over Implicit** — 显式优于隐式

---

## 1) 架构边界（必须）

固定三层，**Rust 是唯一协调者**：

```
React（展示）
    ↓  Tauri IPC
Rust Application Core
    ↓  本机 IPC（契约定义）
Python AI Runtime
```

| 关系 | 状态 |
|------|------|
| React → Rust | ✅ 允许（经 `@desk/platform/ipc`） |
| Rust → Python | ✅ 允许（生命周期 + 业务 IPC） |
| Rust → React | ✅ 允许（Tauri Events 转发流式输出） |
| React → Python | ❌ **禁止**（含 `http://localhost:*` / WebSocket / SSE） |
| React → SQLite | ❌ **禁止** |
| Python → SQLite | ❌ **禁止** |
| Python → React | ❌ **禁止** |
| Python → Tauri | ❌ **禁止** |
| Python → Frontend Event | ❌ **禁止** |

### 1.1 Rust 必须掌控 Python Runtime（硬约束）

- Rust 负责 sidecar **启动 / 停止 / 重启 / 健康检查 / 超时**
- Rust **接管** sidecar stdout/stderr，写入结构化日志（按 `trace_id` / `task_id` 关联）
- Python sidecar 提供仅供 Rust 调用的管理面（`/health`、`/stats`、`/tasks/active`、`/debug/dump`、`/metrics`），契约归档到 `contracts/openapi/sidecar.v1.yaml`
- 流式 token 等业务输出：**Python → Rust → Tauri Events → React**

---

## 2) 契约优先（必须）

`contracts/` 是三端共享 **唯一真相源**（DTO / IPC / HTTP / Event / Error）。

跨端修改流程（**禁止先改实现**）：

```
1. 修改 Contract
       ↓
2. Code Generation
       ↓
3. Rust
       ↓
4. Python
       ↓
5. React
```

- 禁止三端各自维护 DTO（临时原型须在 PR 标注并补契约）
- Breaking Change：新增 `schema/v2`（或新文件）+ `contracts/compatibility/MIGRATION.md`
- 合同 PR：至少 2 人 Approve，并更新 `contracts/CHANGELOG.md`

---

## 3) Feature 边界（必须）

以下 Feature **完全独立**，禁止 Feature 间直接 `import` / `use`：

`chat` · `mail` · `agent` · `workflow` · `knowledge` · `browser` · `ocr` · `mcp` · `plugin` · `tenant` · `user` · `channel`

| 禁止 | 允许 |
|------|------|
| `chat` import `mail` | Query Port（只读跨域查询） |
| `workflow` import `agent` | Event（Pub/Sub） |
| `knowledge` import `chat` | Contract（共享 DTO） |

---

## 4) 六边形架构（必须）

```
UseCase
   ↓
Ports（trait）
   ↓
Infrastructure（storage / vector / file / runtime）
```

**UseCase 禁止：** SQL · HTTP · Filesystem · SQLite · Redis · Environment · Tauri · Python

- 业务用例只依赖 `ports` trait（Repository / Store / Gateway）
- IO 实现只能在 `storage` / `vector` / `file` / `runtime` 层
- 默认本地 SQLite，须保证可替换（Postgres / MySQL / 对象存储 / 向量库）

---

## 5) 模块通信（必须）

| 场景 | 方式 |
|------|------|
| 跨域 / 跨模块写操作 | **Publish / Subscribe**（`kernel::event`） |
| 跨域只读查询 | **Query Port**（trait） |
| 后台任务 | **`kernel::task`**（Scheduler） |

**禁止：** Feature A 直接调用 Feature B · 各模块私开长循环线程

---

## 6) 分端规则

### 6.1 Rust（Application Core）

**负责：** Application · Storage · Python Runtime · Task Scheduler · Event Bus · Permission · Cache · Lifecycle · Logging · Error

| 必须 | 禁止 |
|------|------|
| `Result` + `thiserror` | `unwrap()` / `expect()` / `panic!()` |
| `tracing` | 无限循环线程 |
| trait 抽象 | 阻塞 UI |
| | Feature 之间直接调用 |

### 6.2 Python（AI Runtime）

**允许：** LLM · RAG · OCR · Embedding · MCP · Agent · Browser · Queue · Worker

| 禁止 |
|------|
| GUI · SQLite · Business State · Tauri · React |
| HTTP Server（除非架构评审批准） |

### 6.3 React（展示层）

**负责：** UI · Interaction · State · Theme · Layout · Animation

**必须：**

- **React Compiler** 启用（`babel-plugin-react-compiler`）
- 组件来自 **`@desk/ui`**（shadcn/ui + Radix + Tailwind 令牌）
- Feature UI 走 `@desk/platform/ipc`
- 动画用 **Motion**；图标用 **Lucide**；主题用 **next-themes**

| 禁止 | 说明 |
|------|------|
| Business Logic · SQL · AI Logic · Filesystem | |
| Feature UI 直接 `import @tauri-apps/api` / `invoke()` | |
| Feature 裸 Tailwind（`bg-white`、`rounded-lg` 等） | 用 `<Card variant="glass" />` 等语义组件 |
| Feature 直接引入 Radix / shadcn 源码 | 须经 `@desk/ui` 封装 |

### 6.4 `packages/ui`

**设计系统唯一入口** — Apple 风令牌：Glass · Blur · Backdrop · Motion · Spring · Dynamic Color · Radius · Typography

**封装栈：** shadcn/ui · Radix · Tailwind · Motion · Lucide · TanStack Table/Virtual · Zod + RHF · date-fns · next-themes · dnd-kit · cmdk · Sonner · Monaco

**仅允许：** 组件 · 令牌 · 主题 · 动画 primitives

**禁止：** IPC · Business · Store · API

### 6.5 `packages/platform`

**负责：** IPC · Window · Clipboard · Notification · Shell · File Dialog · OS API · Permission

**禁止：** 业务逻辑

---

## 7) 命名规范（必须）

- 目录 / 模块 / 包名：短、名词优先；**一个词优先，最多两个词**
- 示例：`chat` · `mail` · `agent` · `workflow` · `kernel` · `storage` · `runtime`
- **禁止**作为目录 / crate 名：`*Manager` · `*Service` · `*System` · `*Engine` · `*Processor` · `*Helper` · `*Util`

---

## 8) 分支与协作边界（强约束）

分支名 `<role>/<kind>/<slug>` 决定可改路径；运行 `pnpm branch:sync` 生成 `.cursor/rules/active-branch.mdc`。

| 分支模式 | 职责 |
|----------|------|
| `frontend/<kind>/<slug>` | `apps/desktop/**` · `packages/ui/**` · `crates/**` |
| `python/<kind>/<slug>` | `python/**` |
| `contract/<kind>/<slug>` | `contracts/**` + codegen |
| `main` | 集成（全仓，合并前全量 lint） |

`kind`：`feature` · `fix` · `hotfix` · `chore` · `refactor` · `docs`

创建：`pnpm branch:create frontend feature m5-ui-shell` · 交互：`pnpm branch`

配置：[`tooling/dingda/config/branch_roles.json`](../../tooling/dingda/config/branch_roles.json)

---

## 9) AI 编码约束

AI 助手必须：

- **优先最小修改** — 不一次改多个 Feature
- 修改前先分析影响、确认职责范围
- 不生成未请求代码、不臆测需求

| 禁止 |
|------|
| 大规模重构 · 修改无关文件 · 移动目录 |
| 修改公共 API · 修改命名 · 自动升级依赖 |

---

## 10) Code Review 清单

每次提交前自检：

- [ ] 是否跨层？（React / Rust / Python 边界）
- [ ] 是否跨 Feature？（应走 Event 或 Query Port）
- [ ] 是否修改 Contract？（须先改 `contracts/`）
- [ ] 是否违反六边形？（UseCase 有无 IO）
- [ ] 是否新增循环依赖？
- [ ] 是否需要 Event？
- [ ] 是否需要 Query Port？
- [ ] 是否符合角色职责？
- [ ] `pnpm lint` 是否可通过？

---

## 11) 代码校验（必须）

提交前必须通过对应语言的 lint；CI 强制执行。

| 语言 | 工具 | 命令 |
|------|------|------|
| Frontend | ESLint + TypeScript | `pnpm lint:frontend` |
| Rust | rustfmt + Clippy | `pnpm lint:rust` |
| Python | Ruff（check + format） | `pnpm lint:python` |
| 全量 | 三端一起 | `pnpm lint` |

### Frontend

- 配置：`eslint.config.js`、`tsconfig.lint.json`
- 类型检查：`pnpm lint:types`（已并入 `pnpm lint:frontend`）
- 自动修复：`pnpm lint:frontend:fix`

### Rust

- 格式化：`rustfmt.toml`
- 静态分析：`clippy.toml` + `cargo clippy -D warnings`
- 快捷别名：`.cargo/config.toml`（`cargo lint`、`cargo fmt-check`）
- 自动格式化：`pnpm lint:rust:fix`

### Python

- 配置：根目录 `pyproject.toml` 中 `[tool.ruff]`
- 自动修复：`pnpm lint:python:fix`

### 编辑器与提交钩子

- 换行与缩进：`.editorconfig`、`.gitattributes`（统一 LF）
- 提交前自动校验：Husky + `tooling/scripts/pre-commit.mjs`（仅检查 staged 文件）
- 安装依赖后自动启用：`pnpm install` 会执行 `husky` prepare 脚本
