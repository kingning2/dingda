/**
 * DingDa Tauri 统一入口 — 平台与有锁模式均在此解析。
 *
 * 用法：
 *   pnpm tauri dev                         # 全部平台（xianyu + ali1688）
 *   pnpm tauri dev ali1688                 # 单平台
 *   pnpm tauri dev xianyu,ali1688          # 显式多平台
 *   pnpm tauri build ali1688 locked        # 单平台有锁发行
 *   pnpm tauri dev locked                  # 全部平台有锁开发
 *
 * @author Xiaoman
 * @created 2026-08-22
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { platform } from "node:os";
import { ensureNasm } from "./ensure-nasm.mjs";
import { ensureCmake } from "./ensure-cmake.mjs";
import { ensureSccache } from "./ensure-sccache.mjs";
import {
  applyChannelPlatformEnv,
  isPlatformSelector,
} from "./read-channel-platform.mjs";
import { syncContracts } from "./sync-contracts.mjs";
import { syncPythonWorkspace } from "./sync-python.mjs";

const rootDir = join(dirname(fileURLToPath(import.meta.url)), "../..");
const desktopDir = join(rootDir, "apps/desktop");
const tauriCli = join(desktopDir, "node_modules/@tauri-apps/cli/tauri.js");
const ALL_PLATFORMS = "xianyu,ali1688";
const WINDOWS_MSVC_TRIPLE = "x86_64-pc-windows-msvc";

function printUsage() {
  console.error(`用法: pnpm tauri <dev|build> [platforms] [locked] [tauri 参数...]

  pnpm tauri dev                    全部平台
  pnpm tauri dev ali1688            单平台
  pnpm tauri dev xianyu,ali1688     多平台
  pnpm tauri build ali1688 locked   有锁发行（单平台示例）`);
}

function commandExists(command) {
  const checker = platform() === "win32" ? "where" : "which";
  const result = spawnSync(checker, [command], {
    shell: true,
    stdio: "ignore",
  });
  return result.status === 0;
}

function runNodeScript(scriptPath, args, env) {
  const result = spawnSync(process.execPath, [scriptPath, ...args], {
    cwd: rootDir,
    env,
    stdio: "inherit",
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function readHostTriple() {
  const result = spawnSync("rustc", ["-vV"], {
    cwd: rootDir,
    encoding: "utf8",
    shell: true,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
  const match = result.stdout.match(/^host: (.+)$/m);
  if (!match) {
    process.exit(1);
  }
  return match[1].trim();
}

/**
 * @param {string[]} argv
 * @returns {string | null}
 */
function parseCliTarget(argv) {
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--target" && argv[index + 1]) {
      return argv[index + 1];
    }
    if (arg.startsWith("--target=")) {
      return arg.slice("--target=".length);
    }
  }
  return null;
}

/**
 * @param {string[]} argv
 * @param {string} target
 * @returns {string[]}
 */
function rewriteCliTarget(argv, target) {
  const next = [...argv];
  for (let index = 0; index < next.length; index += 1) {
    const arg = next[index];
    if (arg === "--target" && next[index + 1]) {
      next[index + 1] = target;
      return next;
    }
    if (arg.startsWith("--target=")) {
      next[index] = `--target=${target}`;
      return next;
    }
  }
  next.push("--target", target);
  return next;
}

/**
 * @param {string[]} rawArgv
 */
function parseTauriArgv(rawArgv) {
  const argv = rawArgv.filter((arg) => arg !== "--");
  const command = argv[0];
  if (!command) {
    printUsage();
    process.exit(1);
  }

  let rest = argv.slice(1);
  let platformsArg = ALL_PLATFORMS;

  if (rest.length > 0 && isPlatformSelector(rest[0])) {
    platformsArg = rest[0];
    rest = rest.slice(1);
  }

  let locked = false;
  if (rest.length > 0 && rest[0] === "locked") {
    locked = true;
    rest = rest.slice(1);
  }

  return {
    command,
    platformsArg,
    locked,
    tauriArgs: [command, ...rest],
  };
}

/**
 * @param {string[]} argv
 * @param {NodeJS.ProcessEnv} processEnv
 * @returns {string[]}
 */
function injectPlatformCargoFeatures(argv, processEnv) {
  const command = argv[0];
  if (command !== "dev" && command !== "build") {
    return argv;
  }

  const dashDash = argv.indexOf("--");
  const cargoPart = dashDash >= 0 ? argv.slice(dashDash + 1) : [];
  if (
    cargoPart.some(
      (arg) => arg === "--no-default-features" || arg === "--features",
    )
  ) {
    return argv;
  }
  if (
    argv.some(
      (arg) =>
        arg === "-f" ||
        arg === "--features" ||
        arg.startsWith("--features="),
    )
  ) {
    return argv;
  }

  const platformRaw = processEnv.DINGDA_PLATFORM_CARGO_FEATURES ?? "";
  const extraRaw = processEnv.DINGDA_EXTRA_CARGO_FEATURES ?? "";
  const platforms = platformRaw.split(",").filter(Boolean);
  const extras = extraRaw.split(",").filter(Boolean);

  if (platforms.length === 0 && extras.length === 0) {
    return argv;
  }

  const platformKey = platforms.join(",");
  const isDefaultPlatforms =
    platforms.length === 0 || platformKey === ALL_PLATFORMS;

  if (isDefaultPlatforms) {
    if (extras.length === 0) {
      return argv;
    }
    return [...argv, "-f", extras.join(",")];
  }

  const allFeatures = [...platforms, ...extras].join(",");
  return [
    ...argv,
    "--",
    "--no-default-features",
    "--features",
    allFeatures,
  ];
}

/**
 * @param {NodeJS.ProcessEnv} env
 * @param {"dev" | "build"} command
 * @param {string | null} buildTarget
 */
function prepareLockedBuild(env, command, buildTarget) {
  env.DINGDA_EXTRA_CARGO_FEATURES = "license-lock";

  const verifierScript = join(rootDir, "tooling/scripts/build-license-verifier.mjs");
  const verifierArgs = [];
  if (buildTarget) {
    verifierArgs.push("--target", buildTarget);
  }
  runNodeScript(verifierScript, verifierArgs, env);

  if (command === "dev") {
    const triple =
      platform() === "win32"
        ? (buildTarget ?? WINDOWS_MSVC_TRIPLE)
        : (env.CARGO_BUILD_TARGET ?? readHostTriple());
    const ext = triple.includes("windows") ? ".exe" : "";
    env.LICENSE_VERIFIER_EXE = join(
      rootDir,
      "apps/desktop/src-tauri/binaries",
      `license-verifier-${triple}${ext}`,
    );
    console.log(`[dingda] license-verifier -> ${env.LICENSE_VERIFIER_EXE}`);
  }
}

const { command, platformsArg, locked, tauriArgs: initialTauriArgs } =
  parseTauriArgv(process.argv.slice(2));

const env = ensureSccache({ ...process.env });
applyChannelPlatformEnv(env, platformsArg);

console.log(
  `[dingda] platforms: ${env.DINGDA_CHANNEL_PLATFORMS}${locked ? " (locked)" : ""}`,
);

if (!commandExists("uv")) {
  env.DINGDA_USE_UV = "0";
}

let tauriArgs = [...initialTauriArgs];
const cliTarget = parseCliTarget(tauriArgs);

if (platform() === "win32") {
  ensureNasm(env);
  ensureCmake(env);
  env.RUSTUP_TOOLCHAIN =
    env.RUSTUP_TOOLCHAIN || "stable-x86_64-pc-windows-msvc";
  if (cliTarget) {
    env.CARGO_BUILD_TARGET = cliTarget.includes("windows-gnu")
      ? cliTarget.replace("windows-gnu", "windows-msvc")
      : cliTarget;
    if (cliTarget !== env.CARGO_BUILD_TARGET) {
      tauriArgs = rewriteCliTarget(tauriArgs, env.CARGO_BUILD_TARGET);
    }
  } else if (!env.CARGO_BUILD_TARGET) {
    env.CARGO_BUILD_TARGET = WINDOWS_MSVC_TRIPLE;
  }

  if (!parseCliTarget(tauriArgs) && env.CARGO_BUILD_TARGET) {
    tauriArgs.push("--target", env.CARGO_BUILD_TARGET);
  }
}

const buildTarget = parseCliTarget(tauriArgs) ?? env.CARGO_BUILD_TARGET ?? null;

if (locked && (command === "dev" || command === "build")) {
  prepareLockedBuild(env, command, buildTarget);
}

if (command === "dev" || command === "build") {
  syncContracts({ env });
}
if (command === "dev") {
  syncPythonWorkspace({ env });
}

tauriArgs = injectPlatformCargoFeatures(tauriArgs, env);

if (!existsSync(tauriCli)) {
  console.error(
    "[dingda] @tauri-apps/cli not found in apps/desktop; run pnpm install",
  );
  process.exit(1);
}

const result = spawnSync(process.execPath, [tauriCli, ...tauriArgs], {
  cwd: desktopDir,
  env,
  stdio: "inherit",
});

process.exit(result.status ?? 1);
