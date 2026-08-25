# Naming Guide

## 通用规则

- 短、名词优先
- **一个词优先，最多两个词**
- 行业通用术语

## 禁止后缀（目录 / crate / 包名）

```
Manager · Service · System · Engine · Processor · Helper · Util
```

## 推荐示例

| 类型 | ✅ | ❌ |
|------|----|----|
| Crate | `chat`, `platform`, `infra` | `chatService`, `mailManager` |
| IPC | `chat_list_threads` | `getChatThreads` |
| Event | `chat.message.sent` | `ChatMessageSentEvent` |
| React Feature | `features/chat/` | `features/chat-module/` |
| Python 包 | `gateway`, `worker` | `task_processor` |

## 文件命名

| 语言 | 约定 |
|------|------|
| Rust | `snake_case.rs`, mod 名 snake_case |
| TypeScript | `kebab-case` 目录, `PascalCase` 组件, `camelCase` 函数 |
| Python | `snake_case` 模块与包 |
| Contract | `kebab-case.schema.json` |

## 检查

```bash
python skills/dingda/scripts/check_naming.py
```

## 相关

- [../architecture/principles.md](../architecture/principles.md)
