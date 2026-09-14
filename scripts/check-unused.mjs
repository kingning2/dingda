#!/usr/bin/env node
/**
 * 前端未使用导出 / 孤立文件检查。
 *
 * 职责：
 *     找出「定义了但没有任何地方引用」的导出符号，以及「没有任何文件 import」的源文件。
 *     tsconfig 的 `noUnusedLocals` / `noUnusedParameters` 只管单文件内的局部变量，
 *     跨文件的死代码它看不见 —— 这个脚本补的就是那一层。
 *
 * 设计说明：
 *     - 用 TypeScript Compiler API 做真正的引用分析，不是文本匹配。
 *       正则/字符串计数会把 `index.ts` 的 re-export 全部误判成死代码
 *       （实测：正则法报 25.5%，真实值 0.2%，高估约 100 倍）。
 *     - re-export 链必须先 `getAliasedSymbol` 解析到原始符号，否则
 *       `export { X } from "./x"` 与 `import { X } from "@v2/pkg"` 对不上号。
 *     - 耗时 ≈ tsc --noEmit 同量级（本仓约 3.6s），所以默认不当作硬失败，
 *       也不建议无条件接进 `dev` 前置。
 *     - 组件库与跨语言契约天然有未使用导出，走 `ALLOWLIST` 豁免。
 *     - 本脚本分不清「死代码」与「预留件」。明确标注的预留件（已声明、故意未接线）
 *       不是死代码：要么在文件里写清预留意图，要么加进 `ALLOWLIST`。
 *       反过来，若某个符号已被真实数据源取代（如 mock 常量被 store 取代），
 *       那就是真死代码，应当删掉而不是豁免。
 *
 * 用法：
 *     node scripts/check-unused.mjs            # 默认只警告，退出码 0
 *     node scripts/check-unused.mjs --strict   # 有问题就退出码 1（CI 用）
 *     node scripts/check-unused.mjs --no-allow # 忽略豁免名单，全量报告
 *
 * 已接入启动链（见根 package.json）：
 *     pnpm dev    → 警告模式，不阻塞开发循环
 *     pnpm build  → `--strict`，拦住死代码上线
 *     `pnpm tauri dev` / `pnpm tauri build` 经 tauri.conf.json 的
 *     beforeDevCommand / beforeBuildCommand 调用上面两条，因此一并覆盖。
 *     临时跳过：`SKIP_UNUSED_CHECK=1 pnpm dev`
 *
 * 退出码 0 = 无问题（或仅警告）；1 = 有硬失败项。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** 这些目录下的未使用导出是常态，不是死代码。 */
const ALLOWLIST = [
  // shadcn 风格组件库：提供一堆组件，用哪些由业务决定。
  "packages/client/ui-primitives/src/",
  // 与 Python 的线协议类型：另一侧不写 TS，天然没有 TS 引用。
  "packages/contracts/src/",
];

/** 这些文件是入口，没人 import 它们才正常。 */
const ENTRY_RE = /(?:^|\/)(main|index)\.tsx?$/;

const rel = (f) => path.relative(repoRoot, f).replace(/\\/g, "/");
const isLocal = (f) => f && !f.includes("node_modules") && !f.endsWith(".d.ts");
const exempt = (f) => ALLOWLIST.some((p) => f.startsWith(p));

/**
 * 跑一次全仓引用分析。
 * @returns {{files:number, exports:number, unusedExports:Array, orphans:Array}}
 */
export function analyzeUnused() {
  const configPath = ts.findConfigFile(repoRoot, ts.sys.fileExists, "tsconfig.json");
  if (!configPath) throw new Error("找不到 tsconfig.json");

  const configFile = ts.readConfigFile(configPath, ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(configFile.config, ts.sys, repoRoot);
  const program = ts.createProgram({
    rootNames: parsed.fileNames,
    options: { ...parsed.options, noEmit: true },
  });
  const checker = program.getTypeChecker();
  const sourceFiles = program.getSourceFiles().filter((sf) => isLocal(sf.fileName));

  // 1. 收集导出符号（先解别名，否则 re-export 全误报）
  const exported = new Map();
  const declPos = new Set();

  for (const sf of sourceFiles) {
    const modSym = checker.getSymbolAtLocation(sf);
    if (!modSym) continue;
    for (const ex of checker.getExportsOfModule(modSym)) {
      let sym = ex;
      if (sym.flags & ts.SymbolFlags.Alias) {
        try {
          const t = checker.getAliasedSymbol(sym);
          if (t) sym = t;
        } catch {
          /* 解析失败就保持原符号 */
        }
      }
      const decls = sym.declarations || ex.declarations || [];
      if (!decls.length) continue;
      const d = decls[0];
      if (!isLocal(d.getSourceFile().fileName)) continue;

      const pos = ts.getLineAndCharacterOfPosition(d.getSourceFile(), d.getStart());
      exported.set(sym, {
        name: sym.getName(),
        file: rel(d.getSourceFile().fileName),
        line: pos.line + 1,
      });
      for (const dd of decls) {
        declPos.add(`${dd.getSourceFile().fileName}:${dd.getStart()}`);
      }
    }
  }

  // 2. 遍历所有标识符，命中导出符号且不在声明位置 → 记为使用
  const used = new Set();
  const visit = (node, sf) => {
    if (ts.isIdentifier(node)) {
      const sym = checker.getSymbolAtLocation(node);
      if (sym) {
        let target = sym;
        if (sym.flags & ts.SymbolFlags.Alias) {
          try {
            const t = checker.getAliasedSymbol(sym);
            if (t) target = t;
          } catch {
            target = sym;
          }
        }
        if (exported.has(target) && !declPos.has(`${sf.fileName}:${node.getStart()}`)) {
          used.add(target);
        }
      }
    }
    ts.forEachChild(node, (n) => visit(n, sf));
  };
  for (const sf of sourceFiles) visit(sf, sf);

  // 3. 孤立文件：没有任何模块 import 它，且不是入口
  const imported = new Set();
  for (const sf of sourceFiles) {
    for (const st of sf.statements) {
      if (!((ts.isImportDeclaration(st) || ts.isExportDeclaration(st)) && st.moduleSpecifier)) {
        continue;
      }
      const resolved = ts.resolveModuleName(
        st.moduleSpecifier.text, sf.fileName, parsed.options, ts.sys,
      );
      if (resolved.resolvedModule) imported.add(resolved.resolvedModule.resolvedFileName);
    }
  }

  const orphans = sourceFiles
    .map((sf) => sf.fileName)
    .filter((f) => !imported.has(f) && !ENTRY_RE.test(rel(f)))
    .map(rel);

  const unusedExports = [...exported.entries()]
    .filter(([sym]) => !used.has(sym))
    .map(([, info]) => info)
    .sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line);

  return { files: sourceFiles.length, exports: exported.size, unusedExports, orphans };
}

/**
 * 打印报告。
 * @returns {number} 问题条数（豁免名单内的不计）
 */
export function report(result, { useAllowlist = true } = {}) {
  const ex = useAllowlist
    ? result.unusedExports.filter((i) => !exempt(i.file))
    : result.unusedExports;
  const or = useAllowlist ? result.orphans.filter((f) => !exempt(f)) : result.orphans;

  console.log(`源码文件：${result.files} 个`);
  console.log(`导出符号：${result.exports} 个`);

  console.log(`\n未被引用的导出：${ex.length === 0 ? "无 ✅" : `${ex.length} 个`}`);
  for (const i of ex) console.log(`  ! ${i.file}:${i.line}  ${i.name}`);

  console.log(`\n完全未被 import 的文件：${or.length === 0 ? "无 ✅" : `${or.length} 个`}`);
  for (const f of or) console.log(`  ! ${f}`);

  if (useAllowlist) {
    const skipped =
      result.unusedExports.length - ex.length + (result.orphans.length - or.length);
    if (skipped > 0) console.log(`\n（豁免名单内另有 ${skipped} 项未列出，--no-allow 可查看）`);
  }

  return ex.length + or.length;
}

// CLI 入口
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  if (process.env.SKIP_UNUSED_CHECK) {
    console.log("已设置 SKIP_UNUSED_CHECK，跳过未使用代码检查。");
    process.exit(0);
  }

  const strict = process.argv.includes("--strict");
  const useAllowlist = !process.argv.includes("--no-allow");

  const t0 = Date.now();
  const result = analyzeUnused();
  const problems = report(result, { useAllowlist });
  const ms = Date.now() - t0;

  if (problems > 0) {
    console.log(`\n发现 ${problems} 处未使用代码（耗时 ${ms}ms）。`);
    if (strict) {
      console.log("严格模式：判定为失败。");
      process.exit(1);
    }
    console.log("（默认仅警告；加 --strict 可让 CI 拦截）");
  } else {
    console.log(`\n未使用代码检查通过（耗时 ${ms}ms）。`);
  }
}
