#!/usr/bin/env node
/**
 * E2E 前置产物检查（`pretest` 钩子）。
 *
 * 两个产物缺失都会让测试以**难以定位**的方式失败：
 *   - 没有 `client.exe` → 驱动层（@wdio/tauri-service）报「找不到应用二进制」
 *   - 没有 `apps/web/dist` → 壳起来了但窗口白屏，用例卡在等 `#boot-splash` 消失
 * 与其让使用者去猜，不如在这里直接说清楚该跑哪条命令。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const e2eDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(e2eDir, "..", "..");

const binaryName = process.platform === "win32" ? "client.exe" : "client";

/**
 * 壳二进制路径；必须与 wdio.conf.ts 的 `resolveAppBinary()` 保持一致
 * （那边有为什么需要 `DINGDA_E2E_APP_BINARY` 的完整说明：dev 会话会锁住
 * `target/debug/client.exe`，此时可另建 target 目录）。
 */
function resolveAppBinary() {
  const override = process.env.DINGDA_E2E_APP_BINARY?.trim();
  if (!override) return path.join(repoRoot, "target", "debug", binaryName);
  return path.isAbsolute(override) ? override : path.resolve(repoRoot, override);
}

const checks = [
  {
    label: "Tauri 壳",
    target: resolveAppBinary(),
    fix: "pnpm --filter @v2/e2e build:app",
  },
  {
    label: "前端产物",
    target: path.join(repoRoot, "apps", "web", "dist", "index.html"),
    fix: "pnpm --filter @v2/e2e build:web",
  },
];

const missing = checks.filter((check) => !fs.existsSync(check.target));

if (missing.length > 0) {
  console.error("\nE2E 缺少构建产物：\n");
  for (const check of missing) {
    console.error(`  ✗ ${check.label}`);
    console.error(`      期望路径：${check.target}`);
    console.error(`      修复命令：${check.fix}\n`);
  }
  process.exit(1);
}

console.log("E2E 产物检查通过。");
