# `runtime/tests/`

`src/guards.ts` 的行为测试。

- `guards.test.ts` — 判定器：单值与兜底、多候选顺序、**数组的「先整体再逐元素」顺序**、
  `NaN` / `±Infinity` 的排除、`null` 与数组不算普通对象。

跑：`pnpm test`（工作区根）。

放这里而不放 `src/` 旁边的理由见 [`packages/README.md`](../../../README.md) 的「测试」一节
（`vitest` 是工作区级工具，只在根声明；`check:deps` 只扫 `src/**`）。
