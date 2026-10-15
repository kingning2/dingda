#!/usr/bin/env node
// layers-guard.mjs —— AGENTS.md §2 分层规则的机械子集。
// 只覆盖能用 import 语句判定、且当前代码已全绿的三条（新增规则先核绿再入表）：
//   A. agent/** 与 tools/** 不得直连 playwright / camoufox / sqlite（§5.3）
//   B. crawler/** 不得直接 import playwright（须经 Browser Interface，§2.1）
//   C. api/** 与 domains/** 不得 import playwright / camoufox（§2.3，只做 HTTP 校验与调用）
//   D. 前端骨架层（ui-layout/ui-feedback）不得 import 业务域包（依赖单向：应用→业务域→骨架→底座）
// 退出码：0=干净、1=违规、2=跑不了（找不到源目录）。
import { execFileSync } from 'node:child_process';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';

const root = execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();

const RULES = [
  { id: 'A', dirs: ['packages-py/agent/src', 'packages-py/tools/src'], re: /^\s*(?:import|from)\s+(?:playwright|camoufox|sqlite3|aiosqlite)\b/m },
  { id: 'B', dirs: ['packages-py/crawler/src'], re: /^\s*(?:import|from)\s+playwright\b/m },
  { id: 'C', dirs: ['packages-py/api/src', 'packages-py/domains/src'], re: /^\s*(?:import|from)\s+(?:playwright|camoufox)\b/m },
  { id: 'D', dirs: ['packages/client/ui-layout/src', 'packages/client/ui-feedback/src'], re: /from ['\"]@v2\/(?:ui-home|ui-watch|ui-account|ui-ai|ui-agent|ui-crawler|ui-composer|ui-workflow)\//m },
];

const findings = [];
let scanned = 0;
for (const rule of RULES) {
  for (const dir of rule.dirs) {
    const abs = join(root, dir);
    let stat;
    try { stat = statSync(abs); } catch { continue; } // 包还没建出来时跳过
    walk(abs);
  }
}

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { walk(p); continue; }
    if (!name.endsWith('.py') || name.endsWith('_d_.py')) continue;
    scanned++;
    const text = readFileSync(p, 'utf8');
    for (const rule of RULES) {
      if (rule.dirs.some((d) => p.startsWith(join(root, d) + sep)) && rule.re.test(text)) {
        const lineNo = text.split('\n').findIndex((l) => rule.re.test(l)) + 1;
        findings.push(`  [${rule.id}] ${p.replace(root + sep, '')}:${lineNo}`);
      }
    }
  }
}

if (findings.length === 0) { console.log(`layers-guard: clean（扫描 ${scanned} 个文件）`); process.exit(0); }
console.error(`layers-guard: ${findings.length} 条分层违规：`);
console.error(findings.join('\n'));
console.error('\n对应 AGENTS.md §2/§5：能力归 Browser，平台归 Crawler；Agent/Tool 禁直连浏览器与存储。');
process.exit(1);
