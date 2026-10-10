#!/usr/bin/env node
// floor-guard.mjs —— CONSTRAINTS.md 地板规则的 diff 域守卫。
// 改自 .agents/skills/constraint-driven-development/references/floor-guard.md
// （MIT，授权见 .agents/references/LICENSE-agent-skills）；契约不变：退出码
// 0=干净、1=地板违规（阻断）、2=守卫跑不了（不算干净）。用法：
//   node scripts/check/floor-guard.mjs [--base origin/main]
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const base = (() => {
  const i = process.argv.indexOf('--base');
  return i > -1 ? process.argv[i + 1] : 'origin/main';
})();

// git diff --no-index 在两侧不同时恒退出 1（新文件的常态），这种输出要保留；
// 其余失败一律视为 null，null 永远不能当"干净"。
const git = (args, { diffExit = false } = {}) => {
  try { return execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }); }
  catch (e) { return diffExit && e.status === 1 && typeof e.stdout === 'string' ? e.stdout : null; }
};
const bail = (msg) => { console.error('floor-guard: ' + msg); process.exit(2); };

// 从工作树顶端跑：git ls-files 只列当前子树，子目录里跑会漏别的目录的未跟踪文件。
const top = git(['rev-parse', '--show-toplevel'])?.trim();
if (!top) bail('not inside a git work tree');
process.chdir(top);

const mergeBase = git(['merge-base', base, 'HEAD'])?.trim();
if (!mergeBase) bail('no merge base against ' + base + '（浅克隆先 git fetch）');

const tracked = git(['diff', '--unified=0', mergeBase, '--']);
if (tracked === null) bail('could not diff against ' + mergeBase);
// 未跟踪文件不用 git diff --no-index（Windows 上 /dev/null 不可靠），直接合成等价 diff。
const untrackedFiles = git(['ls-files', '--others', '--exclude-standard']);
if (untrackedFiles === null) bail('could not list untracked files');
const untracked = untrackedFiles.split('\n').filter(Boolean).map((f) => {
  let body = '';
  try { body = readFileSync(f, 'utf8'); } catch { bail('could not read untracked file ' + f); }
  const n = body.split('\n').length;
  const lines = [`diff --git a/${f} b/${f}`, '--- /dev/null', `+++ b/${f}`, `@@ -0,0 +1,${n} @@`];
  for (const l of body.split('\n')) lines.push('+' + l);
  return lines.join('\n');
}).join('\n');
const diff = tracked + '\n' + untracked;

// --- / +++ 只在 diff 行与首个 @@ hunk 之间是文件头；hunk 内全是内容行
const added = [], removed = [], deleted = [];
const pathOf = (s) => s.replace(/^[ab]\//, '');
let file = '', oldFile = '', inHeader = false;
for (const line of diff.split('\n')) {
  if (line.startsWith('diff ')) inHeader = true;
  else if (line.startsWith('@@')) inHeader = false;
  else if (inHeader) {
    if (line.startsWith('--- ')) oldFile = pathOf(line.slice(4));
    else if (line.startsWith('+++ ')) {
      const newFile = pathOf(line.slice(4));
      file = newFile === '/dev/null' ? oldFile : newFile;
      if (newFile === '/dev/null') deleted.push(file);
    }
  }
  else if (line.startsWith('+')) added.push({ file, text: line.slice(1) });
  else if (line.startsWith('-')) removed.push({ file, text: line.slice(1) });
}

const findings = [];
const flag = (rule, f, text) => findings.push({ rule, file: f, text: text.trim().slice(0, 120) });
const isTest = (f) => /\.(test|spec)\.|_test\.|test_/.test(f);
const isConstraints = (f) => /CONSTRAINTS\.md$/.test(f);
// 这些文件"定义"模式（写 suppressed 关键字是为了检查它），内容正则跳过它们，
// 否则守卫首跑会自举报；规则/阈值变化检查不受影响（仍对 CONSTRAINTS.md 生效）。
const isPatternDoc = (f) => isConstraints(f) || /^scripts\/check\//.test(f);
// .constraintsignore：每行一个前缀，命中的文件不再做内容检查（例外请走 CONSTRAINTS.md 例外表）
const ignores = (() => {
  try { return readFileSync('.constraintsignore', 'utf8').split('\n').map((s) => s.trim()).filter(Boolean); }
  catch { return []; }
})();
const isIgnored = (f) => ignores.some((raw) => { const p = raw.replace(/\/+$/, ''); return f === p || f.startsWith(p + '/'); }); // git 路径恒为 /

// 1. 静音检查器。Python 抽象方法 raise NotImplementedError 是正当设计，不在此列；
//    Rust #[allow(dead_code)] 属惯用法，v1 不查。
const SUPPRESSIONS = /@ts-ignore|@ts-expect-error|@ts-nocheck|eslint-disable|biome-ignore|oxlint-disable|# *noqa|# *type: *ignore|istanbul ignore|nosemgrep|gitleaks:allow|Stryker disable/;
// 4. 半成品。Python 只拦"宽 except + pass"静默吞错（窄 except 靠人判断，不误报）。
const STUBS = /throw new (Error|NotImplemented).*[Nn]ot implemented|catch\s*\(\w*\)\s*\{\s*\}|catch\s*\{\s*\}|\bTODO\b|\bFIXME\b|except\s*(Exception|BaseException)?\s*:\s*pass\b/;
// 2. 测试放水（新增 skip）。
const SKIPS = /\.(skip|todo)\b|\bxit\(|\bxdescribe\(|@pytest\.mark\.skip|\btest\.skip|t\.Skip\(/;

for (const { file, text } of added) {
  if (!isPatternDoc(file) && !isIgnored(file)) {
    if (SUPPRESSIONS.test(text)) flag('silenced-checker', file, text);
    if (STUBS.test(text)) flag('unfinished-work', file, text);
    if (SKIPS.test(text)) flag('test-made-easier', file, text);
  }
  // 例外表新增行任何情况下都要报（文档自身也不例外）
  if (isConstraints(file) && /^\| *(W|E)\d+ *\|/.test(text)) flag('new-exception', file, text);
}

// 2b. 测试文件被删；或存活测试文件里的断言被抽走
for (const f of deleted) if (isTest(f)) flag('test-deleted', f, 'file deleted');
for (const { file, text } of removed) {
  if (isTest(file) && !deleted.includes(file) && /\b(expect|assert|should)\b/.test(text)) {
    flag('assertion-removed', file, text);
  }
}

// 1b/2c. CONSTRAINTS.md 规则被削弱或移除（详见上游参考实现的阈值方向配对逻辑）
const ruleKey = (t) => {
  const s = t.trim();
  if (s.startsWith('|')) return s.split('|').map((c) => c.trim()).filter(Boolean)[0] ?? '';
  if (/^[-*] /.test(s)) return s.slice(2).split(':')[0].trim();
  return null; // 散文、标题、日期：不算规则
};
const isException = (t) => /^\| *(W|E)\d+ *\|/.test(t.trim());
const MIN_BEFORE = /(>=|>|≥|at least|minimum|\bmin\b|no less than|not fall|not drop|不得低于|不下降)\s*$/;
const MAX_BEFORE = /(<=|<|≤|at most|maximum|\bmax\b|no more than|under|below|not grow|not exceed|不增长|不得超过)\s*$/;
const MIN_AFTER = /^\s*\S*\s*(or more|or higher|must not fall|must not drop|不得低于|不下降)/;
const MAX_AFTER = /^\s*\S*\s*(or less|or lower|must not grow|must not exceed|不增长|不得超过)/;
const thresholds = (t) => {
  const out = [], re = /\d+(?:\.\d+)?/g;
  let m;
  while ((m = re.exec(t))) {
    const before = t.slice(Math.max(0, m.index - 24), m.index).toLowerCase();
    const after = t.slice(m.index + m[0].length, m.index + m[0].length + 40).toLowerCase();
    const dir = MIN_BEFORE.test(before) || MIN_AFTER.test(after) ? 'min'
      : MAX_BEFORE.test(before) || MAX_AFTER.test(after) ? 'max' : null;
    out.push({ n: Number(m[0]), dir });
  }
  return out;
};
const removedRules = removed.filter((l) => isConstraints(l.file) && ruleKey(l.text) !== null);
const addedRules = added.filter((l) => isConstraints(l.file) && ruleKey(l.text) !== null);
for (const r of removedRules) {
  const a = addedRules.find((x) => ruleKey(x.text) === ruleKey(r.text));
  if (!a) {
    if (!isException(r.text)) flag('rule-removed', r.file, r.text); // 删例外是收紧：静默
    continue;
  }
  const before = thresholds(r.text), after = thresholds(a.text);
  let verdict = null;
  for (const dir of ['min', 'max', null]) {
    const was = before.filter((x) => x.dir === dir), now = after.filter((x) => x.dir === dir);
    was.forEach((b, i) => {
      const n = now[i];
      if (verdict) return;
      if (!n) verdict = 'threshold-removed';
      else if (n.n === b.n) return;
      else if (dir === 'min' ? n.n < b.n : dir === 'max' ? n.n > b.n : true) {
        verdict = dir ? 'threshold-loosened' : 'threshold-changed';
      }
    });
  }
  if (verdict) flag(verdict, r.file, r.text + '  ->  ' + a.text);
}

if (findings.length === 0) { console.log('floor-guard: clean'); process.exit(0); }
console.error('floor-guard: ' + findings.length + ' 条地板违规：');
for (const f of findings) console.error(`  [${f.rule}] ${f.file}: ${f.text}`);
console.error('\n每一条都是"把门槛放低"的动作：修代码，或走 CONSTRAINTS.md 的例外表（带负责人与过期日）。');
process.exit(1);
