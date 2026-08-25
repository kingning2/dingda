# Channel Domain

## 职责

**WhatsApp 桌面辅助（Assist）**，基于 **Baileys 协议桥**（见 [ADR-0006](../../decisions/channel/adr-0006-whatsapp-baileys-worker.md)），不是自动客服。

- 多账号 **QR 协议登录**（dingda-worker）
- 收消息（Worker 同步 → Rust → 桌面 UI）
- 发消息（**人工点击发送** → Rust → Worker 出站队列）
- 会话绑定 `customer_id`（邮箱/手机号关联）
- 为 AI 提供入站消息上下文（翻译、回复建议）
- 消息写入客户时间线

## 非职责

- 自动回复、无人值守发送
- AI 直接调用 WhatsApp 发送
- Meta WhatsApp Business Cloud API / 公网 Webhook（已由 ADR-0006 替代 [ADR-0004](../../decisions/channel/adr-0004-whatsapp-webhook-deployment.md)）
- 邮件（Mail 领域）
- CDP 浏览器镜像（后置评估）

## 稳定边界

```text
dingda-worker（Baileys 协议桥）
  → 标准化入站/出站事件
  → Rust channel UseCase（持久化、幂等）
  → SQLite（channel_account / channel_conversation / channel_message）
  → Tauri Event → React 会话 UI

React 发送
  → IPC channel/send
  → Rust 校验 customer_id + 人工操作标记
  → Worker 发信（非自动队列直发）
```

**当前为规划中领域，未实现；实施时按仓库架构约束落地。**

## 入口

| 类型 | 路径 |
|------|------|
| Rust | `crates/channel/`（骨架） |
| Worker | 规划（`dingda-worker` 已移除，重新引入时实现 `wa_protocol_bridge` job） |
| Contract | `contracts/schema/v1/channel/`（待建） |
| React | `apps/desktop/src/features/channel/`（骨架） |
| Epic 子任务 | [CHG-020](../../changes/2026/07/chg-20260720-020-whatsapp-business-assist.md) |
| ADR | [ADR-0006](../../decisions/channel/adr-0006-whatsapp-baileys-worker.md) |

## 数据模型（MVP 目标）

### `channel_account`

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `label` | 显示名 |
| `phone` | 我方号码 |
| `protocol_status` | `disconnected` / `qr_pending` / `connected` |
| `session_ref` | Worker 会话存储引用 |

### `channel_conversation`

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `customer_id` | 外键 |
| `account_id` | 使用的 WA 账号 |
| `wa_phone` | 对方号码 |
| `last_message_at` | 最近消息时间 |

### `channel_message`

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `conversation_id` | 外键 |
| `direction` | `inbound` / `outbound` |
| `body` | 原文 |
| `translated_body` | 翻译缓存（可选） |
| `wa_message_id` | 协议层幂等键 |
| `sent_by` | 出站均为 `human` |
| `created_at` | 时间 |

## 当前状态

**尚未实现。** Channel 契约、`crates/channel`、`features/channel` 均为规划。ADR-0006 已接受，替代 Business API 方案。

## 当前约束

- **禁止** Agent 工具 `channel.send` 或等价自动发送
- 出站消息必须 `sent_by=human` 且经 UI 显式调用
- Baileys 长连接 **仅在 Worker**；主进程不阻塞 UI
- 依赖 Customer M1/M4 与会话绑定策略
