/**
 * Husky pre-commit：对暂存的 TS / Rust / Python 做 fix + 格式化，并扫描密钥与调试断点。
 *
 * @author Xiaoman
 * @created 2026-08-13
 */
import { spawnSync } from "node:child_process";

function hasCommand(command) {
  const result = spawnSync(command, ["--version"], { shell: true });
  return result.status === 0;
}

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit", shell: true });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function stagedFiles(pattern) {
  const result = spawnSync(
    "git",
    ["diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    { encoding: "utf8" },
  );
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }

  const files = result.stdout
    .trim()
    .split(/\r?\n/)
    .filter(Boolean);

  return pattern ? files.filter((file) => pattern.test(file)) : files;
}

function stagedPatch(file) {
  const result = spawnSync("git", ["diff", "--cached", "--", file], {
    encoding: "utf8",
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
  return result.stdout ?? "";
}

function hasSensitivePattern(text) {
  const patterns = [
    /sk-[a-zA-Z0-9]{20,}/,
    /ghp_[a-zA-Z0-9]{30,}/,
    /AKIA[0-9A-Z]{16}/,
    /api[_-]?key\s*[:=]\s*["'][^"']+["']/i,
    /secret\s*[:=]\s*["'][^"']+["']/i,
  ];
  return patterns.some((pattern) => pattern.test(text));
}

function restage(files) {
  if (files.length === 0) {
    return;
  }
  // Windows cmd.exe 对参数长度有上限；大批量暂存文件时需分批 git add
  const batchSize = 40;
  for (let i = 0; i < files.length; i += batchSize) {
    run("git", ["add", "--", ...files.slice(i, i + batchSize)]);
  }
}

const siteFile = (file) => file.replaceAll("\\", "/").startsWith("site/");
const tsFiles = stagedFiles(/\.(ts|tsx)$/).filter((file) => !siteFile(file));
const rsFiles = stagedFiles(/\.rs$/);
const pyFiles = stagedFiles(/\.py$/);
const allStaged = stagedFiles();

if (tsFiles.length > 0) {
  run("eslint", ["--fix", ...tsFiles]);
  restage(tsFiles);
  run("pnpm", ["lint:types"]);
}

if (rsFiles.length > 0) {
  for (const file of rsFiles) {
    run("rustfmt", ["--edition", "2021", file]);
  }
  restage(rsFiles);
}

if (pyFiles.length > 0) {
  const useUv = hasCommand("uv");
  const runner = useUv ? "uv" : "python";
  const checkArgs = useUv
    ? ["run", "ruff", "check", "--fix", ...pyFiles]
    : ["-m", "ruff", "check", "--fix", ...pyFiles];
  const formatArgs = useUv
    ? ["run", "ruff", "format", ...pyFiles]
    : ["-m", "ruff", "format", ...pyFiles];

  run(runner, checkArgs);
  run(runner, formatArgs);
  restage(pyFiles);
}

for (const file of allStaged) {
  const patch = stagedPatch(file);
  if (hasSensitivePattern(patch)) {
    console.error(
      `[pre-commit] Potential secret detected in staged diff: ${file}. Remove it before commit.`,
    );
    process.exit(1);
  }
  if (/^\+.*\bdebugger\b/m.test(patch)) {
    console.error(`[pre-commit] 'debugger' found in staged diff: ${file}.`);
    process.exit(1);
  }
}
