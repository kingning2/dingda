/**
 * Web 端 E2E（Playwright）：浏览器直连 vite dev + Python Server，不起桌面壳。
 *
 * 与 e2e/（WebdriverIO）的分工：桌面壳层能力（IPC、内嵌 WebDriver、壳装配）继续
 * 归 WebdriverIO；纯 web 渲染与 API 链路走这里 —— web 模式下前端默认连
 * http://127.0.0.1:8787，无需壳注入（runtime/src/server.ts 的 WEB_DEFAULT）。
 *
 * 浏览器用系统 Edge（channel: "msedge"），不下载 Playwright 自带 Chromium。
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-web",
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:1420",
    channel: "msedge",
    viewport: { width: 1920, height: 1080 },
    /** 录制每条用例的完整过程；trace 失败时保留，供 trace viewer 回放排查。 */
    video: { mode: "on", size: { width: 1920, height: 1080 } },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run dingda-v2",
      url: "http://127.0.0.1:8787/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "pnpm --filter @v2/app-web dev",
      url: "http://localhost:1420",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
