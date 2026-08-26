---
id: ADR-0001-ai-readonly-query-port
title: AI 只读 Query Port，禁止直连与写库
status: accepted
domain: customer
created: 2026-07-20
supersedes: none
---

# AI 只读 Query Port，禁止直连与写库

> 执行端**默认在 Rust**。下图「Python Agent」仅在 [ADR-0009](../python-runtime/adr-0009-python-only-when-rust-insufficient.md) 允许的 sidecar 例外下适用。只读 Query Port、禁止写库的结论不变。

## Context

DingDa MVP 要求 AI「记得每个客户」：来源渠道、当前报价、合作状态、沟通摘要。同时用户明确要求：

- AI **可以查询**数据库中的客户与价目信息；
- AI **不能修改**客户数据、报价、合作状态或任何持久化记录。

现有架构约束：Python 不直连 SQLite；Rust 是唯一协调者；业务工具须结构化 ToolCall 经 Rust 授权执行。

若允许 AI 写库，会导致报价/合作状态被模型误改、难以审计，且违背「发送与状态变更由人操作」的产品规则。

## Decision

### 1. AI 数据访问模型

```text
Agent（默认 Rust；仅例外时为 Python sidecar）
  → 结构化 ToolCall（只读工具名 + 参数）
  → Rust Query Port 校验白名单 + 租户/权限 + 参数
  → 只读 SQL / Repository 查询
  → ToolResult（脱敏后的 DTO）
  → 继续生成
```

### 2. 允许的工具（MVP 白名单）

| 工具 ID | 作用 | 返回 |
|---------|------|------|
| `customer.get` | 按 `customer_id` 或 `email` 查单个客户 | 客户 DTO + 合作/报价摘要 |
| `customer.search` | 按邮箱、频道、状态分页搜索 | 客户列表 DTO |
| `customer.timeline` | 某客户最近 N 条沟通摘要 | 时间线条目列表 |
| `pricing.list` | 价目表全量或分页 | 套餐/阶梯 DTO 列表 |
| `pricing.match` | 按条件匹配阶梯（数量、地区等） | 匹配结果 + 说明 |
| `quote.history` | 某客户报价变更历史 | 报价历史 DTO 列表 |

新增只读工具须：Contract 定义 → Rust 实现 → 加入白名单 → Change Record 评审。

### 3. 明确禁止

- Python 连接 SQLite 或读写任何 Rust 管理的存储
- 任何 `create` / `update` / `delete` / `upsert` 类 Agent 工具
- AI 直接触发 SMTP 发送或 WhatsApp 发送
- AI 执行任意 SQL 或动态查询字符串
- 绕过 Rust 从前端把完整 DB  dump 给 Python

### 4. 写操作归属

| 操作 | 执行者 |
|------|--------|
| 创建/编辑客户 | React UI → Rust IPC → UseCase |
| 更新报价、合作状态 | React UI → Rust IPC → UseCase + 审计表 |
| 发送邮件 | React UI → Rust mail-net → SMTP |
| 发送 WhatsApp | React UI → Rust channel → **dingda-worker（Baileys）** |
| 记录沟通时间线 | Rust UseCase（在发信/收信/人工备注时写入） |

### 5. AI 生成前强制上下文

邮件起草、WA 回复建议等 AI 任务，Rust 或 Agent 编排层须：

1. 解析任务中的 `customer_id`（必填）；
2. 调用只读工具拉取客户档案 + 价目表 + 必要时间线；
3. 注入 Prompt；
4. 若客户不存在或缺少关键商务字段，**拒绝生成**并返回可展示的错误码。

不得依赖模型「记忆」跨会话客户信息。

## Alternatives

| 方案 | 未选原因 |
|------|----------|
| Python 只读 SQLite 连接 | 破坏架构边界；难以统一脱敏与审计 |
| AI 可写库但需人工确认 | 增加误写风险；MVP 不需要 |
| 每次把全库 JSON 塞进 Prompt | 不可扩展；泄露风险高 |
| 仅 RAG 向量检索客户 | 无法保证报价/合作字段精确；需结构化查询 |

## Consequences

**正面：**

- 客户数据变更路径单一、可审计
- AI 上下文精确、可复现
- 符合 Rust 协调者架构

**成本：**

- 每个 AI 需查的数据类型须预定义 Contract 与 Query Port
- Agent 编排层须实现「生成前拉上下文」流程

**兼容要求：**

- 所有 MVP Agent 功能 Change 须引用本 ADR
- 架构边界检查应能检测 Python 直连 DB（若尚未覆盖，后续补充规则）
