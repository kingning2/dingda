<!-- 提交前请确认 CI 全绿；大改动建议先开 Issue 讨论 -->

## 动机

<!-- 为什么改？关联 Issue：Fixes #xxx -->

## 改动点

<!-- 一句话/列表说明做了什么 -->

## 验证

<!-- 跑过哪些门禁（pnpm build / pnpm test / ruff+pytest / cargo check）？重构需说明行为不变的验证方式 -->

- [ ] `pnpm build` + `pnpm test`
- [ ] `uv run ruff check packages-py --select E4,E7,E9,F` + `uv run pytest packages-py/api/tests -m "not integration"`
- [ ] `cargo check --workspace --all-targets`
