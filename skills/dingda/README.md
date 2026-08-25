# DingDa AI Development Skill

企业级 AI 智能客服桌面平台的长期维护知识库，供 Cursor Skill、Claude Code Memory、Codex Knowledge 与团队 onboarding 使用。

> **当前阶段：** 基础切片已落地（UI Shell、Rust Agent 组装、渠道接入、Python Sidecar）。新增能力仍须先走契约。

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  React（展示层）                                              │
│  apps/desktop · packages/ui · packages/platform              │
└───────────────────────────┬─────────────────────────────────┘
                            │ Tauri IPC（@desk/platform/ipc）
┌───────────────────────────▼─────────────────────────────────┐
│  Rust Application Core（唯一协调者，默认实现含 AI）            │
│  crates/* · apps/desktop/src-tauri                           │
│  crates/{agent,platform,infra,common,ports,macros,adapter}   │
│  business（应用胶水）· apps/desktop/src-tauri（应用壳）        │
└───────────────────────────┬─────────────────────────────────┘
                            │ 仅当 Rust 生态不够（ADR-0009）
┌───────────────────────────▼─────────────────────────────────┐
│  Python Sidecar（例外，不是 AI Runtime）                       │
│  python/sidecar · python/channels                            │
└─────────────────────────────────────────────────────────────┘
```

### 核心原则

| 原则 | 说明 |
|------|------|
| **Rust First** | 默认用 Rust 实现（含 AI）；Python 只补生态缺口 |
| **Contracts First** | `contracts/` 是跨端唯一真相源 |
| **Hexagonal Architecture** | UseCase → Ports → Infrastructure |
| **Feature Boundary** | Feature 垂直独立，禁止互相 import |
| **Event Driven** | 跨模块写操作走 Pub/Sub（`infra::event`） |
| **Local / Offline First** | 默认本地 SQLite，核心能力可离线 |
| **Dependency Inward** | 依赖指向内层，Infrastructure 不反向依赖 UseCase |

### 禁止的跨层调用

| 禁止 | 原因 |
|------|------|
| React → Python | Rust 是唯一协调者 |
| React → SQLite | 存储由 Rust 负责 |
| Python → SQLite | 存储由 Rust 负责 |
| Python → React / Tauri | Python 不知道前端 |
| 未论证就把 AI 放 Python | 默认用 Rust（ADR-0009） |
| Feature A → Feature B（直接 import） | 须走 Event 或 Query Port |

### 跨端变更顺序

```
contracts/  →  codegen  → 受影响端（默认 Rust → React；涉及 sidecar 才改 Python）
```

---

## 目录结构

```
skills/dingda/
├── README.md                 # 本文件
├── architecture/             # 架构设计文档
├── guides/                   # 分端与横切规范
├── recipes/                  # 操作手册（AI 按步骤执行）
├── templates/                # 可复制骨架（无业务逻辑）
├── scripts/                  # 脚手架与架构检查
└── examples/                 # 最佳实践示例
```

---

## 如何使用

### 对于 AI 助手

1. **识别任务** — 新增 Feature？改 Contract？加 IPC？**改 UI？**
2. **读 Recipe / Guide** — UI 任务先读 `guides/ui-reference.md`；其他见 `recipes/<task>.md`
3. **用 Template** — 从 `templates/` 复制骨架，不凭空造结构
4. **跑 Script** — `python skills/dingda/scripts/create_*.py` 生成标准目录
5. **验证** — `check_architecture.py` + `lint_all.py`

### 对于开发者

```bash
# 生成新 Feature 骨架
python skills/dingda/scripts/create_feature.py --name myfeature

# 生成新 Python 包并注册 workspace（须先论证 Rust 生态不够）
python skills/dingda/scripts/create_python_package.py --name mypackage

# 生成 Rust ↔ Python sidecar IPC 骨架（仅例外能力）
python skills/dingda/scripts/create_rust_python_ipc.py --feature agent --action ping

# 架构合规检查
python skills/dingda/scripts/check_architecture.py

# 全量 lint
python skills/dingda/scripts/lint_all.py

# 项目树
python skills/dingda/scripts/generate_tree.py
```

### 与仓库其他文档的关系

| 文档 | 关系 |
|------|------|
| `.cursor/rules/master.md` | 基线规则（本 Skill 的权威来源之一） |
| `contracts/` | 运行时契约（本 Skill 的 templates/contract 对齐此处） |
| `docs/architecture/` | ADR 与架构补充 |
| `skills/dingda/guides/xianyu-mtop-discovery.md` | 闲鱼 mtop 抓包发现流程与已接入接口表 |

### 平台专项 Guides

| 指南 | 用途 |
|------|------|
| [`guides/ui-reference.md`](guides/ui-reference.md) | **UI 首选参考** — Shadcn Admin + Aceternity UI + `@desk/ui` 三层 |
| [`guides/ui-design-system.md`](guides/ui-design-system.md) | 设计令牌、组件映射、Emil 动效 |
| [`guides/frontend.md`](guides/frontend.md) | 前端技术栈与目录约定 |
| [`guides/xianyu-mtop-discovery.md`](guides/xianyu-mtop-discovery.md) | 闲鱼 Web 接口抓包、登记、Rust 接入 |

---

## AI Coding Rules

1. **最小修改** — 不一次改多个 Feature
2. **先分析后动手** — 列出影响范围与职责归属
3. **禁止臆测** — 不生成未请求代码
4. **禁止绕架构** — 不为方便直连 Python / SQLite；不为方便把 AI 放到 Python
5. **契约先行** — 跨端字段变更先改 `contracts/`

### Code Review Checklist

- [ ] 是否跨层？
- [ ] 是否跨 Feature？
- [ ] 是否先改了 Contract？
- [ ] 是否违反六边形？
- [ ] 是否新增循环依赖？
- [ ] 是否需要 Event / Query Port？
- [ ] 是否符合角色职责（frontend / rust / python）？
- [ ] `pnpm lint` 是否通过？

---

## Feature 列表

`chat` · `agent` · `knowledge` · `workflow` · `browser` · `ocr` · `mcp` · `plugin` · `tenant` · `user` · `channel`

---

## 三人协作边界

按 **分支名前缀** 约束 scope（见 `pnpm branch:sync` → `active-branch.mdc`）。

| 分支前缀 | 范围 |
|----------|------|
| `frontend/*` | `apps/desktop/**` · `packages/ui/**` · `packages/platform/**` · `crates/**` |
| `python/*` | `python/**` |
| `contract/*` | `contracts/**` |
| 共同 | `contracts/` 变更必须评审 |

创建分支：`pnpm branch` · 配置：[`config/branch_roles.json`](config/branch_roles.json)

---

## 扩展本 Skill

- 新增 Recipe：在 `recipes/` 添加 `<action>.md`，同步更新本 README 索引
- 新增 Template：在 `templates/<type>/` 添加 README + 骨架文件
- 新增检查：在 `scripts/check_*.py` 添加规则，`check_architecture.py` 聚合调用
- 架构变更：先更新 `architecture/`，再更新 `.cursor/rules/master.md`
