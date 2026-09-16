#!/usr/bin/env node
/**
 * E2E 一键入口：先重编译前端 + 壳，再跑 WebdriverIO。
 *
 * 用法（仓库根）：
 *   pnpm e2e
 *   pnpm e2e -- --spec ./specs/ai-codex-sandbox.spec.ts
 *   pnpm e2e -- --spec ./specs/desktop-smoke.spec.ts
 *
 * 环境变量：
 *   DINGDA_E2E_SKIP_BUILD=1     跳过编译，只跑（产物仍须存在）
 *   CARGO_TARGET_DIR            默认 target-e2e（避开 tauri dev 锁住的 target/debug）
 *   DINGDA_E2E_APP_BINARY       默认随 CARGO_TARGET_DIR 指向 debug/client
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptsDir = path.dirname(fileURLToPath(import.meta.url));
const e2eDir = path.resolve(scriptsDir, "..");
const repoRoot = path.resolve(e2eDir, "..");
const binaryName = process.platform === "win32" ? "client.exe" : "client";

function log(message) {
  console.log(`[e2e] ${message}`);
}

function run(command, args, { cwd = e2eDir, env = process.env } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env,
      stdio: "inherit",
      shell: process.platform === "win32",
    });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (signal) {
        reject(new Error(`${command} 被信号中断：${signal}`));
        return;
      }
      if (code !== 0) {
        reject(new Error(`${command} ${args.join(" ")} 退出码 ${code}`));
        return;
      }
      resolve();
    });
  });
}

function prepareEnv() {
  const env = { ...process.env };
  // 默认独立 target，避免与 `pnpm tauri dev` 抢 client.exe
  if (!env.CARGO_TARGET_DIR?.trim()) {
    env.CARGO_TARGET_DIR = path.join(repoRoot, "target-e2e");
  }
  if (!env.DINGDA_E2E_APP_BINARY?.trim()) {
    const binary = path.join(env.CARGO_TARGET_DIR, "debug", binaryName);
    // 相对仓库根，与 wdio.conf / require-artifacts 约定一致
    env.DINGDA_E2E_APP_BINARY = path.relative(repoRoot, binary);
  }
  return env;
}

async function main() {
  const rawArgs = process.argv.slice(2);
  const wdioArgs = rawArgs[0] === "--" ? rawArgs.slice(1) : rawArgs;
  const skipBuild = process.env.DINGDA_E2E_SKIP_BUILD === "1";
  const env = prepareEnv();

  log(`壳产物：${env.DINGDA_E2E_APP_BINARY}（CARGO_TARGET_DIR=${env.CARGO_TARGET_DIR}）`);

  if (skipBuild) {
    log("DINGDA_E2E_SKIP_BUILD=1，跳过编译");
  } else {
    log("编译前端 apps/web/dist …");
    await run("pnpm", ["run", "build:web"], { env });
    log("编译壳 cargo build -p client --features e2e …");
    await run("pnpm", ["run", "build:app"], { env });
    log(
      "提示：若 packages-rs/client/gen/schemas/ 出现 wdio 相关 diff，提交前请还原：" +
        "git checkout -- packages-rs/client/gen/schemas/",
    );
  }

  await run("node", [path.join(scriptsDir, "require-artifacts.mjs")], { env });

  log(`启动 wdio${wdioArgs.length ? ` ${wdioArgs.join(" ")}` : "（全部 spec）"} …`);
  await run("pnpm", ["exec", "wdio", "run", "wdio.conf.ts", ...wdioArgs], { env });
}

main().catch((error) => {
  console.error(`[e2e] 失败：${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
});
