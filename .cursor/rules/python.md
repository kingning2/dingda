# Python Rules（Developer C）

适用范围：`python/**`

## 职责边界

- Python 是 **AI Runtime / Sidecar**（gateway → queue → worker → provider），只被 Rust `runtime` 调用
- **禁止**直连 SQLite/关系库、React、Tauri；业务数据由 Rust 注入上下文
- **禁止** import `apps/`、`crates/`、`packages/` 源码

## 目录

```
python/
├── sidecar/           # HTTP 服务（Rust 管理生命周期）
└── packages/          # 共享 Python 包
```

## 运行时分层（必须）

- `gateway`：HTTP API（契约校验、鉴权、限流、SSE）
- `queue`：任务队列与背压（可替换实现）
- `worker`：Worker 池与并发控制
- `provider`：模型 Provider 注册表与路由（新增 Provider 不改业务 executor）
- `llm/rag/ocr/agent/browser/workflow`：能力包（短名）

## 命名规范

- package 用短名名词：`gateway`、`queue`、`worker`、`provider`
- 禁止：`*_engine_provider_service`、`browser_automation_runtime`

## 契约与兼容

- Request/Response/Events/Errors 必须来自 `contracts/` codegen（`python/packages/contracts`）
- 字段新增以可选为主；Breaking Change 先改 `contracts/schema/v2` 并提供迁移说明，再运行 `sync_contracts.py`

## 日志

- 结构化 JSON 日志；`trace_id` 由 Rust 传入或从 header 解析
- 禁止 `print()` 调试残留

## 相关

- [`docs/managed/domains/python-runtime/README.md`](../../docs/managed/domains/python-runtime/README.md)
- [`docs/managed/architecture/README.md`](../../docs/managed/architecture/README.md)
