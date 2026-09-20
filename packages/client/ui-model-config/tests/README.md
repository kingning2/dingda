# `ui-model-config/tests/`

`src/model-credential-view.ts` 的行为测试。

- `model-credential-view.test.ts` — 标题 / 副标题的兜底、地址取主机名、相对时间的边界
  （`0` 与 `null` 都按「未检测」处理）、**请求体里该不该出现某个字段**
  （编辑时 key 留空必须不带 `api_key`，地址留空必须落成 `null`）、表单校验
  （编辑态允许 key 留空，新建态不允许）、**模型列表**（`ok=false` 收成 `failed`、
  空 id 被过滤、卡片顺序沿用上游、默认徽章只挂一个、选中项不在列表时补到最前、
  四态文案不留空、`modelFetchPlan` 在「编辑态换了供应商」时必须改用新 key）。

最后两类是重点：字段多传一个、少传一个都是合法类型，`tsc` 看不见，但行为完全不同 ——
多传一个空 `api_key` 会把 key 写坏；而「该用哪把 key 拉模型」判错，会把「还没填新 key」
报成「API key 无效」。

跑：`pnpm test`（工作区根）。

放这里而不放 `src/` 旁边的理由见 [`packages/README.md`](../../../README.md) 的「测试」一节
（`vitest` 是工作区级工具，只在根声明；`check:deps` 只扫 `src/**`）。
