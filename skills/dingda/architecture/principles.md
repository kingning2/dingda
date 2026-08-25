# Design Principles

DingDa 所有设计必须遵守以下原则。违反即视为架构错误。

## First Principles

### 1. Contracts First

`contracts/` 是跨端唯一真相源。任何 DTO、IPC、HTTP、Event、Error 字段变更必须先改契约，再 codegen，再改受影响实现端（默认 Rust / React；仅 sidecar 例外才改 Python）。

### 2. Feature First

系统按 Feature 垂直切分（`chat`、`agent`、`knowledge` 等）。每个 Feature 拥有独立的 crate、前端模块、契约命名空间。Feature 之间禁止直接依赖。

### 3. Dependency Inward

依赖方向永远指向内层：

```
Presentation → Application → Domain → Ports ← Infrastructure
```

外层可以知道内层接口；内层不得依赖外层实现。

### 4. Event Driven

跨 Feature 的写操作与状态传播通过 `infra::event` Pub/Sub。禁止 Feature A 直接调用 Feature B 的 UseCase 或 Repository。

### 5. Local First

默认所有数据与计算在本地完成。SQLite 为默认存储，向量与文件均在本地目录。云端同步为可选扩展，不得作为默认路径。

### 6. Offline First

核心客服能力（查看历史、草稿、本地知识库索引）在无网络时仍可用。AI 推理依赖模型可用性，但 UI 与本地数据访问不得因断网崩溃。

### 7. Testable by Design

UseCase 只依赖 Port trait，测试时注入 Mock。禁止在 UseCase 中硬编码 SQLite 或 HTTP 客户端。

### 8. Composition over Inheritance

Rust 用 trait 组合；React 用 hooks 与组件组合；Python 用协议与依赖注入。禁止深层继承树。

### 9. Explicit over Implicit

错误类型显式（`thiserror`）；IPC 命令显式注册；Event 名称显式定义在契约中。禁止魔法字符串散落代码库。

### 10. Rust First

默认用 Rust 实现能力（含 AI / LLM）。Python Sidecar 只补 Rust 生态缺口，不是 AI Runtime。新增 `python/**` 须在 Change Record 写明缺口。

## 原则冲突时的优先级

```
Contracts First  >  Feature Boundary  >  Layer Boundary  >  Convenience
```

不得为方便而绕过契约或 Feature 边界。

## 相关文档

- [layers.md](layers.md)
- [dependency.md](dependency.md)
- [../guides/review.md](../guides/review.md)
