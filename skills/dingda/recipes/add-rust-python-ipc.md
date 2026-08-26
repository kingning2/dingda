# Recipe: Add Rust ↔ Python IPC

仅当 ADR-0009 例外（Rust 生态不够）时，新增一条 Rust 调用 Python sidecar 的 HTTP 接口。默认 AI / 业务不要走 sidecar。

## 修改顺序

| 步骤 | 操作 |
|------|------|
| 1 | 运行 `create_rust_python_ipc.py` |
| 2 | 编辑 contract schema 字段 |
| 3 | 确认 OpenAPI path fragment |
| 4 | 实现 Rust `SidecarClient` HTTP（TODO） |
| 5 | 实现 Python handler 逻辑（骨架阶段保持空） |
| 6 | Rust 在 UseCase 中调用 `runtime::sidecar` |
| 7 | `pnpm lint` |

## 命令

```bash
# 标准 POST 接口
python skills/dingda/scripts/create_rust_python_ipc.py --feature agent --action ping

# 流式任务（额外生成 stream.rs 骨架）
python skills/dingda/scripts/create_rust_python_ipc.py --feature agent --action run_task --streaming --dry-run
```

## 生成文件

```
contracts/schema/v1/<feature>/sidecar/<action>.{request,response}.schema.json
contracts/openapi/sidecar.paths/<feature>_<action>.yaml
crates/infra/src/sidecar/client.rs          # 首次创建
crates/infra/src/sidecar/routes/<feature>_<action>.rs
python/packages/gateway/src/gateway/handlers/<feature>_<action>.py
python/runtime/ipc.py                         # 路由注册
skills/dingda/examples/rust-python/<feature>_<action>/README.md
```

## 禁止修改

- React 直连 sidecar URL
- Python 向前端发事件
- 跳过 contract 自定义 JSON 字段

## 验证

```bash
python skills/dingda/scripts/check_boundary.py
python skills/dingda/scripts/check_layers.py
pnpm lint
```

## Checklist

- [ ] request/response schema 成对
- [ ] OpenAPI fragment 已生成
- [ ] Rust route 在 `runtime/src/sidecar/routes/`
- [ ] Python handler 在 `gateway/handlers/`
- [ ] `routes.py` 已注册
- [ ] 无业务逻辑（Skeleton 阶段）

## 参考示例

[../examples/rust-python/](../examples/rust-python/)
