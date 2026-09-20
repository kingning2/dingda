/**
 * Vitest 配置（工作区根）。
 *
 * 职责：
 *   跑各包 `tests/` 下的纯逻辑测试。
 *
 * 设计说明：
 *   - **测试放包的 `tests/`，不放 `src/` 旁边。** 原因不是偏好：`vitest` 与
 *     `typescript` / `vite` 同级，属**工作区级工具，只在根 package.json 声明**；
 *     而 `scripts/check-workspace-deps.mjs` 只扫 `src/**` 与包根 `*.config.*`。
 *     把测试放进 `src/` 就会让「用了没声明」硬失败，逼着每个包都声明 vitest。
 *   - **不配 alias。** `@v2/*` 走 pnpm 工作区软链解析 —— 与 `vite.config.ts` 同一条
 *     约定（那里明确写了「刻意不在这里加别名，否则会掩盖工作区是否真的接通」）。
 *   - `environment: "node"`：目前测的都是纯函数。要测组件再按需换 jsdom。
 *   - `e2e/` 已随 WebdriverIO 套件移除；`e2e-web/` 走 Playwright，不在 include 范围内。
 */
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["packages/*/tests/**/*.test.ts", "packages/*/*/tests/**/*.test.ts"],
    environment: "node",
  },
});
