# Event Bus

DingDa 使用 Rust `infra::event` 作为跨 Feature 通信的事件总线。

## 架构位置

```
Feature A (publish)  →  infra::event  →  Feature B (subscribe)
                              ↑
                        contracts/event/
                        （payload 定义）
```

## 设计规则

1. **Event 名称与 payload 必须在 `contracts/` 定义**
2. **Publisher 不知道 Subscriber** — 只发布到 bus
3. **Subscriber 幂等** — 同一事件多次投递应安全
4. **禁止** Feature 间为传递数据而新增同步函数调用

## Event 分类

| 类型 | 示例 | 说明 |
|------|------|------|
| Domain Event | `chat.message.sent` | 业务事实，不可变 |
| Integration Event | `knowledge.index.requested` | 跨 Feature 协作 |
| System Event | `runtime.sidecar.restarted` | 基础设施状态 |

## 命名约定

```
<feature>.<entity>.<past-tense-verb>

示例：
  chat.message.sent
  knowledge.index.completed
  agent.task.completed
```

## 契约结构

```
contracts/schema/v1/<feature>/event/<name>.schema.json
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dingda://chat/event/message.sent/v1",
  "type": "object",
  "required": ["event_id", "thread_id", "occurred_at"],
  "properties": {
    "event_id": { "type": "string", "format": "uuid" },
    "thread_id": { "type": "string" },
    "occurred_at": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

## Rust 骨架（无业务逻辑）

```rust
// crates/infra/src/event/mod.rs — 概念示意
pub trait EventBus: Send + Sync {
    fn publish(&self, topic: &str, payload: &[u8]) -> Result<(), EventError>;
    fn subscribe(&self, topic: &str, handler: Box<dyn EventHandler>) -> Result<SubscriptionId, EventError>;
}
```

## 与 Tauri Events 的区别

| | infra::event | Tauri Events |
|---|---------------|--------------|
| 范围 | Rust 进程内跨 Feature | Rust → React |
| 定义 | contracts/schema event | contracts IPC event forward |
| 消费者 | Rust Subscriber | React listener |

流式 AI token：**默认 Rust → Tauri Events → React**。仅 sidecar 例外时才是 Python → Rust → Tauri Events → React。不经过 infra event bus 直达前端。

## 相关文档

- [../recipes/add-event.md](../recipes/add-event.md)
- [../guides/events.md](../guides/events.md)
- [contracts.md](contracts.md)
