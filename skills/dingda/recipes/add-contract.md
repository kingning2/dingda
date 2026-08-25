# Recipe: Add Contract

## 修改顺序

1. `python skills/dingda/scripts/create_contract.py --feature X --name Y --kind dto|ipc|event|error`
2. 编辑 schema 字段
3. `python skills/dingda/scripts/sync_contracts.py`
4. 更新受影响端引用（默认 Rust / TS；涉及 sidecar 才改 Python）
5. `python skills/dingda/scripts/check_contracts.py`

## 禁止

- 先改 TS/Rust/Python 再补 schema
- 未文档化字段
- Breaking 变更不写 MIGRATION

## Checklist

- [ ] `$id` 正确
- [ ] `required` 完整
- [ ] 2+ reviewer（PR）

## 模板

[../templates/contract/](../templates/contract/)
