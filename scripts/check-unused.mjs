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
 *     - 组件库与跨语言契约天然有未使用导出，走 `ALLOWLIST`（按文件路径前缀）豁免。
 *     - 本脚本分不清「死代码」与「预留件」。明确标注的预留件（已声明、故意未接线）
 *       不是死代码：要么在文件里写清预留意图，要么加进 `RESERVED`（按 文件+符号）。
 *       反过来，若某个符号已被真实数据源取代（如 mock 常量被 store 取代），
 *       那就是真死代码，应当删掉而不是豁免。
 *
 * 已知坑（改本脚本前必读）：
 *     判定「未使用」要比对**标识符节点**起点，所以排除声明自身时必须用
 *     `decl.name.getStart()`，不能用 `decl.getStart()`。原因是：
 *       - `export const X` —— 声明节点是 `VariableDeclaration`（不含 `export`，
 *         那属于父级 `VariableStatement`），起点恰好等于标识符起点，用哪个都对；
 *       - `export function/interface/type/class/enum X` —— 声明节点**包含 `export`
 *         修饰符**，起点在 `export` 上，与标识符起点差 7 个字符，于是
 *         `declPos.has(...)` 恒为 false，把自己的标识符当成一次「使用」→ 永不报出。
 *     这个缺陷曾让本脚本对后一类导出**系统性漏报**，给出「0 未使用」的虚假信心。
 *     见下方 `nameStart()`。
 *
 * 用法：
 *     node scripts/check-unused.mjs            # 默认只警告，退出码 0
 *     node scripts/check-unused.mjs --strict   # 有问题就退出码 1（CI 用）
 *     node scripts/check-unused.mjs --no-allow # 忽略豁免与预留名单，全量报告
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

/**
 * 测试文件：由测试框架按 glob 发现，没人 import 它们才是正常的。
 *
 * 注意它们**仍参与**「谁引用了哪个导出」的分析 —— 只被测试引用的导出不算死代码
 * （测试就是它的消费方）。这里只把它们从「孤立文件」里排除。
 */
const TEST_RE = /\.test\.[cm]?tsx?$/;

/**
 * 已定性为「预留件」的未使用导出：机制是活的，只是当前没有调用方。
 *
 * 与 ALLOWLIST 的区别 —— ALLOWLIST 按**文件路径前缀**豁免（整类文件天然没有引用，
 * 例如 shadcn 组件库）；这里按**文件 + 符号**豁免，且每项必须写清为什么它是预留而不是死代码。
 *
 * 纪律（写死在这里，加新项前先读一遍）：
 *   - 若某符号已被别的实现取代（如 mock 常量被 store 取代、非流式版被 SSE 版取代），
 *     那是**真死代码**，应该删掉，**不要**加进来。
 *   - 若某符号是某个活跃机制的对称接口（另一半在用），可以加进来并注明。
 *   - 每项都要能回答：「删了它，哪段活代码会变成孤儿？」
 */
const RESERVED = [
  // ── 活跃机制的对称接口：删了会让另一半失去配对的注册/读取入口 ──
  {
    file: "packages/client/runtime/src/http-client.ts",
    name: "onApiRequest",
    why: "请求拦截器注册入口。requestInterceptors 仍在 http-client.ts:118 被消费，删掉它这套机制就失去唯一注册点。与 onApiResponse（在用）对称。",
  },
  {
    file: "packages/client/runtime/src/app-alert.ts",
    name: "getAppAlerts",
    why: "告警快照读取。与 subscribeAppAlerts / pushAppAlert（均在用）同属一个活跃机制。",
  },
  {
    file: "packages/client/runtime/src/app-alert.ts",
    name: "clearAppAlerts",
    why: "清空全部告警，同上机制的对称操作。",
  },
  {
    file: "packages/client/runtime/src/dismiss-boot-splash.ts",
    name: "dismissBootSplashAfterPaint",
    why: "双 rAF 后再移除启动屏的变体（等 React 提交到 DOM，避免闪白）。dismissBootSplash 被 boot-gate.tsx 直接调用；本变体是预留的更稳妥时序。",
  },
  {
    file: "packages/client/ui-ai/src/session.ts",
    name: "clearWorkSnapshot",
    why: "清除会话快照。与 stashWorkSnapshot / peekWorkSnapshot（均在用）同属一个活跃机制。",
  },
  {
    file: "packages/client/ui-crawler/src/product-preview.ts",
    name: "closeProductPreviewUi",
    why: "关闭预览。与 openProductPreview / subscribeProductPreview（均在用）同属一个活跃机制。",
  },

  // ── 成套 API：成套的判定器，缺一个就会有人再手写一遍 typeof 判断 ──
  {
    file: "packages/client/runtime/src/guards.ts",
    name: "isNumber",
    why: "成套判定器的一员（isString / isNumber / isBoolean / isObject / isArray / isFunction）。当前无调用方，但缺了它调用点会手写 `typeof x === \"number\"` —— 那样会把 NaN / Infinity 放进来。",
  },
  {
    file: "packages/client/runtime/src/guards.ts",
    name: "isBoolean",
    why: "成套判定器的一员。当前无调用方；缺了它调用点会手写 typeof 判断（且容易漏掉包装对象与字符串 \"true\" 的区别）。",
  },
  {
    file: "packages/client/runtime/src/guards.ts",
    name: "isFunction",
    why: "成套判定器的一员。当前无调用方；用于判定外部传入的回调是否为函数（如 Tauri 注入的钩子）。",
  },

  // ── 待用户定性：疑为被取代的实现，我倾向删除，但不在本轮擅自删 ──
  {
    file: "packages/client/ui-account/src/mock-data.ts",
    name: "accountFromAuthProbe",
    why: "【待定性·倾向删除】登录态探活后的账号快照构造，属 mock 期产物；账号已接真实后端。",
  },
  {
    file: "packages/client/ui-account/src/mock-data.ts",
    name: "mockAccountAfterQrLogin",
    why: "【待定性·倾向删除】已标 @deprecated（改用 accountFromQrLogin），且无调用方。",
  },
  {
    file: "packages/client/ui-crawler/src/crawler-api.ts",
    name: "searchCrawlerProducts",
    why: "【待定性·倾向删除】非流式搜品，已被 searchCrawlerProductsLive（SSE 版，在用）取代。",
  },
  {
    file: "packages/client/ui-crawler/src/crawler-api.ts",
    name: "fetchCrawlerProductLive",
    why: "【待定性·倾向删除】直播拉详情，从未接线；UI 走的是非流式的 fetchCrawlerProduct（在用）。",
  },
  {
    file: "packages/client/ui-crawler/src/crawler-api.ts",
    name: "crawlerLiveFrameToDataUrl",
    why: "【待定性·倾向删除】纯转发壳：函数体只有 `return frameToDataUrl(frame)`。",
  },
];

const reservedKey = (file, name) => `${file}:${name}`;
const RESERVED_INDEX = new Map(RESERVED.map((r) => [reservedKey(r.file, r.name), r.why]));

const rel = (f) => path.relative(repoRoot, f).replace(/\\/g, "/");
const isLocal = (f) => f && !f.includes("node_modules") && !f.endsWith(".d.ts");
const exempt = (f) => ALLOWLIST.some((p) => f.startsWith(p));

/**
 * 取声明节点的「标识符起点」，不是声明节点起点。
 *
 * 必须用标识符起点，因为比对用的是 `node.getStart()`（标识符节点）。
 * 两者在下列情况下不同：
 *   - `export function/interface/type/class/enum X` —— 声明节点**包含 `export` 修饰符**，
 *     起点在 `export` 上，与标识符起点差 7 个字符
 *   - `export const X` —— 声明节点是 `VariableDeclaration`（不含 `export`，那属父级
 *     `VariableStatement`），起点恰好等于标识符起点
 * 曾经用声明节点起点，导致前一类导出把自己的标识符当成一次「使用」而永不报出。
 */
const nameStart = (d) => (d.name ? d.name.getStart() : d.getStart());

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

      const pos = ts.getLineAndCharacterOfPosition(d.getSourceFile(), nameStart(d));
      exported.set(sym, {
        name: sym.getName(),
        file: rel(d.getSourceFile().fileName),
        line: pos.line + 1,
      });
      for (const dd of decls) {
        declPos.add(`${dd.getSourceFile().fileName}:${nameStart(dd)}`);
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
    .filter((f) => !imported.has(f) && !ENTRY_RE.test(rel(f)) && !TEST_RE.test(f))
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
  const reserved = useAllowlist
    ? result.unusedExports.filter((i) => RESERVED_INDEX.has(reservedKey(i.file, i.name)))
    : [];
  const reservedSet = new Set(reserved.map((i) => reservedKey(i.file, i.name)));

  const ex = useAllowlist
    ? result.unusedExports.filter((i) => !exempt(i.file) && !reservedSet.has(reservedKey(i.file, i.name)))
    : result.unusedExports;
  const or = useAllowlist ? result.orphans.filter((f) => !exempt(f)) : result.orphans;

  console.log(`源码文件：${result.files} 个`);
  console.log(`导出符号：${result.exports} 个`);

  console.log(`\n未被引用的导出：${ex.length === 0 ? "无 ✅" : `${ex.length} 个`}`);
  for (const i of ex) console.log(`  ! ${i.file}:${i.line}  ${i.name}`);

  console.log(`\n完全未被 import 的文件：${or.length === 0 ? "无 ✅" : `${or.length} 个`}`);
  for (const f of or) console.log(`  ! ${f}`);

  // 预留件单独列出并带理由 —— 是债务，不是豁免；不静默隐藏。
  if (reserved.length > 0) {
    console.log(`\n已定性为预留、不计入问题：${reserved.length} 个`);
    for (const i of reserved) {
      console.log(`  ~ ${i.file}:${i.line}  ${i.name}`);
      console.log(`      ${RESERVED_INDEX.get(reservedKey(i.file, i.name))}`);
    }
  }

  if (useAllowlist) {
    const skipped =
      result.unusedExports.length - ex.length - reserved.length + (result.orphans.length - or.length);
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
