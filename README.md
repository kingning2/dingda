# DingDa

本地优先的 **AI Agent 智能客服** 桌面应用。面向电商卖家的多平台接待与运营工作台：把闲鱼、1688、小红书等平台的账号、会话与商品数据收进一个本地桌面端，用 AI 完成买家接待、比价调研与知识检索——数据与密钥全程留在本机。

---

## 它能做什么

### 🔌 多平台多账号接入
- **扫码登录**：闲鱼 / 1688 / 小红书，扫码即登录，支持多账号并存
- **会话保活**：Cookie 浏览器续期、登录态探针、批量会话状态查询
- **长连接收发**：闲鱼 WebSocket 挂机收消息、会话历史、消息推送

### 🤖 AI 买家接待
- 基于关键词规则 + LLM 的**买家意图识别**（咨询 / 议价 / 售后 / 闲聊 / 无需回复）
- **自动回复**：按意图生成回复，支持自定义话术、议价轮次上限与折扣区间控制
- **免打搅策略**：不礼貌消息过滤、无需回复场景静默、AI 关闭时降级为固定话术

### 📊 比价与选品调研 Agent
- LangGraph 流程编排：**规划 → 关键词提炼 → 多平台搜索 → 分析 → 匹配 → 结论沉淀**
- 跨闲鱼 / 1688 自动采集同款商品，产出比价结论
- 全流程步骤可观测（trace / 步骤回调），支持运行暂停、恢复与取消

### 🧠 知识库（RAG）
- 文档切分、向量化、检索、重排一条龙
- 本地向量存储（Qdrant / SQLite 可选），为 AI 回复注入店铺自有知识

### ⚙️ 模型与插件
- OpenAI 兼容协议接入任意厂商：密钥校验、余额查询、模型列表
- 本地 OCR 插件、本地 Embedding，按需安装

### 🖥️ 桌面工作台（本地优先）
- 仪表盘 · 商品 · 利润 · 监控 · 任务 · 设置
- 数据落本地 SQLite（Rust 管理），AI 只读、不写库，消息发送仅由人工触发
- 进程级生命周期管理：Sidecar 崩溃自动重启、组件健康检查、有序关闭

## 架构

```text
React（展示）  →  Tauri IPC  →  Rust（协调者，默认实现含 AI）
                                  ↓ 仅当 Rust 生态不够
                               Python Sidecar（浏览器自动化 / LangGraph）
```

- **Rust 是唯一协调者**：持有全部业务数据（SQLite）、生命周期与权限门禁
- **Python Sidecar 只补生态缺口**：Playwright / Camoufox 浏览器自动化与 LangGraph 流程，经命名管道 / 共享内存与 Rust 通信
- **契约先行**：`contracts/` 内 JSON Schema 是跨端接口的唯一真相源，一条命令生成 TypeScript / Rust / Python 三端类型

## 仓库结构

```text
apps/desktop        Tauri + React 桌面应用
  └─ src-tauri      Rust 后端（core 生命周期 · infrastructure · domain · commands）
packages            前端共享包（ui · platform · store · contracts · utils）
python              Python Sidecar（src/dingda_sidecar 单包：agent · runtime · channels · browser · common）
contracts           跨端契约（JSON Schema，唯一真相源）
tooling/dingda      分支规则与契约 codegen
subscription        激活 / 授权工具
docs/managed        架构 · Domain · ADR · Change Record
```

## 快速开始

环境要求：Node.js ≥ 20、pnpm、Rust stable（MSVC）、Python 3.13 + [uv](https://docs.astral.sh/uv/)

```bash
pnpm install          # 安装前端依赖（Python 侧由 uv 托管）
pnpm tauri dev        # 本地开发（默认闲鱼 + 1688 平台）
```

发行构建（含 NSIS 安装包）：

```bash
pnpm tauri build locked
```

质量检查：

```bash
pnpm lint             # 三端全量：ESLint + tsc + clippy + ruff
pnpm lint:fix         # 自动修复
cargo test -p dingda --lib              # Rust 单测
cd python && uv run python -m pytest tests   # Sidecar 单测
```

多平台按需组合（平台特性在 Rust / 前端按条件编译裁剪）：

```bash
pnpm tauri dev ali1688,xiaohongshu
```

## 契约与分支工作流

- 修改跨端接口**先改 `contracts/schema/`**，再运行生成器同步三端类型（构建时自动执行）
- 分支名决定职责边界：`frontend/*` · `python/*` · `contract/*` · `main`，详见 [`pnpm branch:sync`](tooling/dingda/)
- 架构叙事唯一入口：[`docs/managed/architecture/README.md`](docs/managed/architecture/README.md)

## License

[待定](LICENSE) —— 发布前补充。

<!-- TODO: 开源前补充 LICENSE 文件与截图/演示 GIF -->
