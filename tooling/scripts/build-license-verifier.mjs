import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  chmodSync,
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { platform } from "node:os";
import { ensurePerl } from "./ensure-perl.mjs";
import { ensureSccache } from "./ensure-sccache.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const subscriptionDir = join(root, "subscription");
const binariesDir = join(root, "apps/desktop/src-tauri/binaries");
const infraGeneratedDir = join(root, "crates/infra/generated");

/** 本机 Windows 默认 MSVC triple（仅当未指定 --target / 环境变量时）。 */
const WINDOWS_DEFAULT_MSVC_TRIPLE = "x86_64-pc-windows-msvc";

function parseArgs(argv) {
  const options = { target: null, force: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--force") {
      options.force = true;
      continue;
    }
    if (arg === "--target") {
      options.target = argv[index + 1] ?? null;
      index += 1;
      continue;
    }
    if (arg.startsWith("--target=")) {
      options.target = arg.slice("--target=".length);
    }
  }
  return options;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? root,
    stdio: "inherit",
    shell: true,
    env: options.env ?? process.env,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function readHostTriple() {
  const result = spawnSync("rustc", ["-vV"], {
    cwd: root,
    encoding: "utf8",
    shell: true,
  });
  if (result.status !== 0) {
    console.error("failed to read rustc host triple");
    process.exit(result.status ?? 1);
  }
  const match = result.stdout.match(/^host: (.+)$/m);
  if (!match) {
    console.error("could not parse rustc host triple");
    process.exit(1);
  }
  return match[1].trim();
}

/**
 * Windows GNU → 同架构 MSVC；保留 i686 / aarch64 等 arch。
 *
 * @param {string} triple
 * @returns {string}
 */
function forceWindowsMsvc(triple) {
  if (triple.includes("windows-gnu")) {
    return triple.replace("windows-gnu", "windows-msvc");
  }
  if (triple.includes("windows") && !triple.includes("windows-msvc")) {
    return WINDOWS_DEFAULT_MSVC_TRIPLE;
  }
  return triple;
}

/**
 * 解析构建目标：CLI --target > Tauri/Cargo 环境变量 > 本机默认。
 *
 * @param {string | null} requested
 * @returns {string}
 */
function resolveBuildTriple(requested) {
  const fromEnv =
    process.env.TAURI_ENV_TARGET_TRIPLE ||
    process.env.CARGO_BUILD_TARGET ||
    null;
  const raw =
    requested ??
    fromEnv ??
    (platform() === "win32" ? WINDOWS_DEFAULT_MSVC_TRIPLE : readHostTriple());

  if (platform() === "win32" || raw.includes("windows")) {
    const forced = forceWindowsMsvc(raw);
    if (forced !== raw) {
      console.warn(`WARNING: rewriting Windows target ${raw} -> ${forced}`);
    }
    return forced;
  }
  return raw;
}

function artifactName(targetTriple) {
  const ext = targetTriple.includes("windows") ? ".exe" : "";
  return `license-verifier-${targetTriple}${ext}`;
}

function sourceBinaryName(targetTriple) {
  return targetTriple.includes("windows")
    ? "license-verifier.exe"
    : "license-verifier";
}

function sha256File(filePath) {
  const hash = createHash("sha256");
  hash.update(readFileSync(filePath));
  return hash.digest("hex");
}

const SUBSCRIPTION_WATCH_PATHS = [
  "Cargo.toml",
  "Cargo.lock",
  "build.rs",
  "src",
  "keys",
];

/** 递归取路径（文件或目录树）最新 mtime；跳过 target。 */
function latestMtimeMs(path) {
  if (!existsSync(path)) {
    return 0;
  }
  const stat = statSync(path);
  if (!stat.isDirectory()) {
    return stat.mtimeMs;
  }

  let latest = stat.mtimeMs;
  const stack = [path];
  while (stack.length > 0) {
    const current = stack.pop();
    let entries;
    try {
      entries = readdirSync(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (entry.name === "target") {
        continue;
      }
      const fullPath = join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
        continue;
      }
      try {
        latest = Math.max(latest, statSync(fullPath).mtimeMs);
      } catch {
        // 并发删除时忽略
      }
    }
  }
  return latest;
}

/** subscription 源码树最新修改时间。 */
function subscriptionLatestMtimeMs() {
  let latest = 0;
  for (const segment of SUBSCRIPTION_WATCH_PATHS) {
    latest = Math.max(latest, latestMtimeMs(join(subscriptionDir, segment)));
  }
  return latest;
}

/**
 * 判断是否需要重新 cargo build / 复制到 Tauri binaries。
 *
 * @returns {{ needsBuild: boolean, needsCopy: boolean, latestSubscription: number }}
 */
function resolveVerifierSyncState(destPath, sourcePath, force) {
  const latestSubscription = subscriptionLatestMtimeMs();

  if (force) {
    return { needsBuild: true, needsCopy: true, latestSubscription };
  }

  const destExists = existsSync(destPath);
  const sourceExists = existsSync(sourcePath);
  const destMtime = destExists ? statSync(destPath).mtimeMs : 0;
  const sourceMtime = sourceExists ? statSync(sourcePath).mtimeMs : 0;

  const needsBuild = !sourceExists || latestSubscription > sourceMtime;
  const needsCopy =
    !destExists || !sourceExists || sourceMtime > destMtime || needsBuild;

  return { needsBuild, needsCopy, latestSubscription };
}

function syncSha256Sidecars(destPath) {
  const shaPath = join(infraGeneratedDir, "license_verifier.sha256");
  mkdirSync(infraGeneratedDir, { recursive: true });
  const previous = existsSync(shaPath)
    ? readFileSync(shaPath, "utf8").trim()
    : "";
  const destMtime = existsSync(destPath) ? statSync(destPath).mtimeMs : 0;
  const shaMtime = existsSync(shaPath) ? statSync(shaPath).mtimeMs : 0;
  if (previous && destMtime > 0 && shaMtime >= destMtime) {
    return previous;
  }
  const digest = sha256File(destPath);
  writeFileSync(shaPath, `${digest}\n`, "utf8");
  if (previous !== digest) {
    console.log(`sha256 -> ${shaPath} (${digest})`);
  }
  return digest;
}

const { target: targetArg, force: forceBuild } = parseArgs(process.argv.slice(2));

const env = ensureSccache({ ...process.env });
if (platform() === "win32") {
  // 宿主编译器固定 MSVC；交叉目标（如 i686）靠 --target，不要改成 gnu。
  env.RUSTUP_TOOLCHAIN =
    env.RUSTUP_TOOLCHAIN ?? "stable-x86_64-pc-windows-msvc";
  ensurePerl(env);
}

const buildTriple = resolveBuildTriple(targetArg);
const destPath = join(binariesDir, artifactName(buildTriple));
const releaseDir = join(subscriptionDir, "target", buildTriple, "release");
const sourcePath = join(releaseDir, sourceBinaryName(buildTriple));

if (!existsSync(subscriptionDir)) {
  console.error(`subscription crate missing at ${subscriptionDir}`);
  process.exit(1);
}

const { needsBuild, needsCopy, latestSubscription } = resolveVerifierSyncState(
  destPath,
  sourcePath,
  forceBuild,
);

if (!needsBuild && !needsCopy) {
  console.log(`license-verifier up to date: ${destPath}`);
  syncSha256Sidecars(destPath);
  process.exit(0);
}

if (needsBuild) {
  const cargoArgs = [
    "build",
    "--release",
    "--bin",
    "license-verifier",
    "--target",
    buildTriple,
  ];
  const reason = forceBuild
    ? "forced rebuild"
    : `subscription touched ${new Date(latestSubscription).toISOString()}`;
  console.log(`building license-verifier for ${buildTriple} (${reason})`);
  run("cargo", cargoArgs, { cwd: subscriptionDir, env });
} else {
  console.log(`license-verifier release binary fresh; syncing copy only`);
}

if (!existsSync(sourcePath)) {
  console.error(`license-verifier binary not found at ${sourcePath}`);
  process.exit(1);
}

mkdirSync(binariesDir, { recursive: true });
mkdirSync(infraGeneratedDir, { recursive: true });

cpSync(sourcePath, destPath);
if (!buildTriple.includes("windows")) {
  chmodSync(destPath, 0o755);
}
console.log(`license-verifier -> ${destPath}`);

if (platform() === "win32") {
  const staleGnu = join(
    binariesDir,
    "license-verifier-x86_64-pc-windows-gnu.exe",
  );
  if (existsSync(staleGnu)) {
    unlinkSync(staleGnu);
    console.log(`removed stale alias ${staleGnu}`);
  }
}

const digest = syncSha256Sidecars(destPath);

const attestPath = join(infraGeneratedDir, "license_attest_key.hex");
if (!existsSync(attestPath)) {
  console.error(
    `missing ${attestPath}; subscription build.rs should write it from public_key.pem`,
  );
  process.exit(1);
}

console.log(`sha256 verified (${digest})`);
console.log(`attest key -> ${attestPath}`);
