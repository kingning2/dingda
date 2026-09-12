#!/usr/bin/env node
/**
 * 前端工作区依赖卫生检查。
 *
 * 拆包之后「依赖必须声明在使用它的包里」成了硬约束，但违反它的代价是**静默的**：
 * 靠根级 hoisting 兜着，本地能跑、CI 能过，直到某天换个安装方式或挪个目录才炸。
 * 这个脚本把这类问题变成显式报错。
 *
 * 检查五项：
 *   1. 环            —— @v2/* 之间不许成环
 *   2. 跨层引用      —— 包不许 import 应用源码（apps/**），方向只能是 app → package（**硬失败**）
 *   3. 用了没声明    —— 源码/样式/配置里引了，但 package.json 里没写（**硬失败**）
 *   4. 声明没用      —— package.json 里写了，但源码里找不到（警告）
 *   5. 自依赖        —— 包依赖自己（**硬失败**）
 *
 * 扫描范围：`src/**` 的 .ts/.tsx/.css，加上包根的 `*.config.{ts,js,mjs,cjs}`。
 * 之所以要带上配置文件：`vite.config.ts` 用了 vite / 插件，那些依赖属于这个包，
 * 只扫 src 会把它们误判成「声明没用」。
 *
 * 别名处理：`@web/*` 这类只存在于 tsconfig `paths` 里的前缀**不是包**。若脚本把它们
 * 当成外部包，应用自己用 `@web/*` 会被误报成「用了没声明」。所以先查 paths：
 *   - 命中别名且落在**本包**目录内 → 内部引用，忽略
 *   - 命中别名且落在**别的包**目录内 → 跨层引用，硬失败
 *   - 命中别名但落在 packages/ 下（即本身就是工作区包）→ 走常规依赖检查
 *
 * 用法：
 *   node scripts/check-workspace-deps.mjs
 * 退出码 0 = 通过；1 = 有硬失败项。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Node 内置模块，不参与依赖检查。 */
const NODE_BUILTINS = new Set([
  "assert", "buffer", "child_process", "cluster", "console", "crypto", "dgram",
  "dns", "events", "fs", "http", "https", "module", "net", "os", "path",
  "process", "punycode", "querystring", "readline", "stream", "string_decoder",
  "timers", "tls", "tty", "url", "util", "v8", "vm", "worker_threads", "zlib",
]);

/**
 * 这些包用 JSX 时不需要显式 import（编译成 react/jsx-runtime），
 * 所以「声明了但源码里找不到」不算错。
 */
const IMPLICIT_WHEN_TSX = new Set(["react", "react-dom"]);

const IMPORT_PATTERNS = [
  /\bfrom\s*["']([^"']+)["']/g,
  /\bimport\s*\(?\s*["']([^"']+)["']/g,
  /\brequire\s*\(\s*["']([^"']+)["']/g,
];
const CSS_IMPORT_RE = /@import\s+(?:url\(\s*)?["']([^"']+)["']/g;

function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

/** 收集一个包要扫描的文件。 */
function collectFiles(pkgDir) {
  const files = [];
  const walk = (dir) => {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === "node_modules" || entry.name === "dist") continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(ts|tsx|css)$/.test(entry.name)) files.push(full);
    }
  };
  walk(path.join(pkgDir, "src"));
  for (const name of fs.readdirSync(pkgDir)) {
    if (/\.config\.(ts|js|mjs|cjs)$/.test(name)) {
      files.push(path.join(pkgDir, name));
    }
  }
  return files;
}

/** 从一段源码里抽出所有 import 的包名（未归一化）。 */
function extractSpecifiers(src, isCss) {
  const out = [];
  const patterns = isCss ? [CSS_IMPORT_RE] : IMPORT_PATTERNS;
  for (const re of patterns) {
    for (const match of stripComments(src).matchAll(re)) {
      out.push(match[1]);
    }
  }
  return out;
}

/** 归一化到包名：`@tauri-apps/api/core` → `@tauri-apps/api`，`react/jsx-runtime` → `react`。 */
function toPackageName(spec) {
  const parts = spec.split("/");
  return spec.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
}

function isExternal(spec) {
  if (spec.startsWith(".") || spec.startsWith("/") || spec.startsWith("node:")) return false;
  if (spec.startsWith("data:") || spec.startsWith("http")) return false;
  return !NODE_BUILTINS.has(spec);
}

/**
 * 读 tsconfig 的 `paths`，产出别名表：`@web/` → `<abs>/apps/web/src/`。
 *
 * 只登记「目标不在 packages/ 下」的别名 —— 目标是 packages/ 的那些其实就是工作区包名
 * （`@v2/ui-layout` → `./packages/client/ui-layout/src/index.ts`），走常规依赖检查即可，
 * 混进来会让「引用了另一个包」被误判成跨层。
 */
function loadAliases() {
  const tsconfigPath = path.join(repoRoot, "tsconfig.json");
  if (!fs.existsSync(tsconfigPath)) return [];
  const raw = fs.readFileSync(tsconfigPath, "utf8").replace(/\/\/[^\n]*/g, "");
  const paths = JSON.parse(raw).compilerOptions?.paths ?? {};
  const packagesDir = path.join(repoRoot, "packages");

  const aliases = [];
  for (const [key, targets] of Object.entries(paths)) {
    const target = Array.isArray(targets) ? targets[0] : targets;
    if (typeof target !== "string") continue;
    const abs = path.resolve(repoRoot, target);
    if (abs.startsWith(packagesDir + path.sep)) continue;
    // `@web/*` → 前缀 `@web/`；`@web` → 精确匹配。
    const wildcard = key.endsWith("/*");
    aliases.push({
      prefix: wildcard ? key.slice(0, -1) : key,
      exact: !wildcard,
      dir: wildcard ? path.dirname(abs) : abs,
    });
  }
  // 长前缀优先：`@v2/app-web/` 应比 `@v2/` 先命中。
  aliases.sort((a, b) => b.prefix.length - a.prefix.length);
  return aliases;
}

/** 收集工作区内的所有包。 */
function collectWorkspacePackages() {
  const packages = [];
  const visit = (dir, depth) => {
    if (depth > 3 || !fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory() || entry.name === "node_modules") continue;
      const full = path.join(dir, entry.name);
      const manifestPath = path.join(full, "package.json");
      if (fs.existsSync(manifestPath)) {
        const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
        if (typeof manifest.name === "string" && manifest.name.length > 0) {
          packages.push({ dir: full, name: manifest.name, manifest });
        }
      }
      visit(full, depth + 1);
    }
  };
  visit(path.join(repoRoot, "packages"), 0);
  visit(path.join(repoRoot, "apps"), 0);
  return packages;
}

const packages = collectWorkspacePackages();
const workspaceNames = new Set(packages.map((p) => p.name));
const aliases = loadAliases();

/** 别名解析：返回命中别名的目标目录，未命中返回 null。 */
function resolveAlias(spec) {
  for (const alias of aliases) {
    if (alias.exact ? spec === alias.prefix : spec.startsWith(alias.prefix)) {
      return alias.dir;
    }
  }
  return null;
}

/** 找出某个目录属于哪个工作区包（按目录前缀最长匹配）。 */
function ownerOf(absDir) {
  let best = null;
  for (const pkg of packages) {
    if (absDir === pkg.dir || absDir.startsWith(pkg.dir + path.sep)) {
      if (!best || pkg.dir.length > best.dir.length) best = pkg;
    }
  }
  return best;
}

const graph = new Map();
const failures = [];
const warnings = [];

for (const pkg of packages) {
  const declared = new Map();
  for (const field of ["dependencies", "devDependencies", "peerDependencies"]) {
    for (const dep of Object.keys(pkg.manifest[field] ?? {})) {
      declared.set(dep, field);
    }
  }

  const used = new Set();
  const crossLayer = new Set();
  let hasTsx = false;
  for (const file of collectFiles(pkg.dir)) {
    const isCss = file.endsWith(".css");
    if (!isCss && file.endsWith(".tsx")) hasTsx = true;
    for (const spec of extractSpecifiers(fs.readFileSync(file, "utf8"), isCss)) {
      if (!isExternal(spec)) continue;
      const name = toPackageName(spec);

      // 工作区包名之外的裸前缀（如 @web/*）只可能来自 tsconfig paths 别名。
      if (!workspaceNames.has(name)) {
        const aliasDir = resolveAlias(spec);
        if (aliasDir) {
          const owner = ownerOf(aliasDir);
          if (owner && owner.name !== pkg.name) {
            crossLayer.add(`${spec}（属于 ${owner.name}）`);
          }
          continue;
        }
      }

      if (name === pkg.name) {
        failures.push(`${pkg.name}  自依赖：源码里引了 ${spec}`);
        continue;
      }
      used.add(name);
    }
  }

  if (crossLayer.size) {
    failures.push(
      `${pkg.name}  跨层引用应用源码：${[...crossLayer].sort().join(", ")}` +
        `\n      → 包不能依赖 apps/**。把实现挪进本包，或改为由应用注入。`,
    );
  }

  const undeclared = [...used].filter((d) => !declared.has(d)).sort();
  // peerDependencies 只声明运行环境，不要求源码里直接 import（如 zustand 需要 react，
  // 但 app-state 自己不写 JSX），所以不参与「声明没用」的判定。
  const unused = [...declared.entries()]
    .filter(([dep, field]) => field !== "peerDependencies")
    .map(([dep]) => dep)
    .filter((d) => !used.has(d) && !(hasTsx && IMPLICIT_WHEN_TSX.has(d)))
    .sort();

  if (undeclared.length) {
    failures.push(`${pkg.name}  用了没声明：${undeclared.join(", ")}`);
  }
  if (unused.length) {
    warnings.push(`${pkg.name}  声明没用：${unused.join(", ")}`);
  }

  graph.set(
    pkg.name,
    [...used].filter((d) => workspaceNames.has(d) && declared.has(d)).sort(),
  );
}

// 环检测（DFS 三色）
const WHITE = 0, GRAY = 1, BLACK = 2;
const color = new Map([...graph.keys()].map((name) => [name, WHITE]));
const cycles = [];
const stack = [];

function dfs(node) {
  color.set(node, GRAY);
  stack.push(node);
  for (const next of graph.get(node) ?? []) {
    if (!graph.has(next)) continue;
    if (color.get(next) === GRAY) {
      cycles.push([...stack.slice(stack.indexOf(next)), next].join(" → "));
    } else if (color.get(next) === WHITE) {
      dfs(next);
    }
  }
  stack.pop();
  color.set(node, BLACK);
}
for (const node of graph.keys()) {
  if (color.get(node) === WHITE) dfs(node);
}

const leaves = [...graph.entries()].filter(([, deps]) => deps.length === 0).map(([n]) => n);

console.log(`工作区包：${packages.length} 个`);
console.log(`叶子包：${leaves.sort().join(" · ")}`);
console.log(`环：${cycles.length === 0 ? "无 ✅" : ""}`);
for (const cycle of cycles) console.log(`  ✗ ${cycle}`);
if (cycles.length) failures.push(`存在循环依赖（${cycles.length} 条）`);

console.log(`\n用了没声明 / 跨层引用：${failures.length === 0 ? "无 ✅" : ""}`);
for (const item of failures) console.log(`  ✗ ${item}`);

console.log(`\n声明没用（警告）：${warnings.length === 0 ? "无 ✅" : ""}`);
for (const item of warnings) console.log(`  ! ${item}`);

if (failures.length > 0) {
  console.log("\n依赖检查未通过。");
  process.exit(1);
}
console.log("\n依赖检查通过。");
