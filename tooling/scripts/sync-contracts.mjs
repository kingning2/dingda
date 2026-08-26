/**
 * 将 contracts/schema 同步为三端 codegen（Rust / TS / Python）。
 *
 * @author Xiaoman
 * @created 2026-08-19
 */
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { platform } from "node:os";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const SYNC_SCRIPT = join(root, "tooling/dingda/scripts/sync_contracts.py");

/**
 * @param {string} command
 * @returns {boolean}
 */
function commandExists(command) {
  const checker = platform() === "win32" ? "where" : "which";
  const result = spawnSync(checker, [command], {
    shell: true,
    stdio: "ignore",
  });
  return result.status === 0;
}

/**
 * @returns {string | null}
 */
function resolvePythonCommand() {
  if (commandExists("python")) {
    return "python";
  }
  if (commandExists("python3")) {
    return "python3";
  }
  return null;
}

/**
 * 在仓库根目录执行 `sync_contracts.py`。
 *
 * @param {{ cwd?: string, env?: NodeJS.ProcessEnv }} [options]
 * @returns {boolean}
 */
export function syncContracts(options = {}) {
  const python = resolvePythonCommand();
  if (!python) {
    console.error(
      "[dingda] python not found; cannot sync contracts. Install Python 3.10+.",
    );
    process.exit(1);
  }

  console.log("[dingda] syncing contracts (schema → Rust / TS / Python)...");
  const result = spawnSync(python, [SYNC_SCRIPT, "--quiet"], {
    cwd: options.cwd ?? root,
    env: options.env ?? process.env,
    stdio: "inherit",
    shell: true,
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }

  return true;
}

const isDirectRun =
  Boolean(process.argv[1]) &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  syncContracts();
}
