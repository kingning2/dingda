# `ui-ai/tests/`

聊天渲染与工具输出解析的行为测试。测的都是**纯函数** —— 这正是把它们从组件里抽出来的理由。

- `schedule.test.ts` — 轮次切分、timeline 交错顺序、流式标记的三条边界、
  新旧格式分流、异常数据（孤儿消息 / 查不到的 step id）
- `agent-output.test.ts` — 工具输出的容错解析：多候选 url 回落、单 item 载荷归一、
  数字 id 不丢、comments 逐条容错、比价累积轮次

跑：`pnpm test`（工作区根）。

放这里而不放 `src/` 旁边的理由见 [`packages/README.md`](../../../README.md) 的「测试」一节
（`vitest` 是工作区级工具，只在根声明；`check:deps` 只扫 `src/**`）。

**回归重点**：`agent-output.test.ts` 里带「【回归】」字样的用例对应一个真出过的 bug ——
判定器的数组语义颠倒导致 `items` 数组被当成候选列表，商品 / 比价 / comments
全部静默清空。改 `runtime/guards.ts` 前先看那两条。
