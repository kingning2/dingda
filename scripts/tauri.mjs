#!/usr/bin/env node
/**
 * Tauri CLI 包装：把 Rust 应用目录指向 packages-rs/client。
 *
 * Tauri v2 默认只认 `<cwd>/src-tauri`。本仓库把 Tauri 壳放在 `packages-rs/client`，
 * 故通过官方支持的 `TAURI_APP_PATH` 环境变量告知 CLI
 * （见 tauri-cli `helpers/app_paths.rs::resolve_tauri_dir`）。
 *
 * 用法与 `tauri` 完全一致：
 *   pnpm tauri dev
 *   pnpm tauri build
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const appPath = join(repoRoot, "packages-rs", "client");

if (!existsSync(join(appPath, "tauri.conf.json"))) {
  console.error(`[tauri] 未找到 Tauri 应用目录：${appPath}`);
  process.exit(1);
}

const bin = join(
  repoRoot,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "tauri.CMD" : "tauri",
);

if (!existsSync(bin)) {
  console.error("[tauri] 未安装 @tauri-apps/cli，请先执行 pnpm install");
  process.exit(1);
}

const child = spawn(bin, process.argv.slice(2), {
  stdio: "inherit",
  cwd: repoRoot,
  env: { ...process.env, TAURI_APP_PATH: appPath },
  shell: process.platform === "win32",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
