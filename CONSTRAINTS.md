# Constraints（质量约束）

> 写代码前先读本文件；**不得为让某次改动通过而放宽本文件**。
> 放宽 = 删规则、降阈值、删测试、加静音注释 —— 一律走例外表（带负责人与过期日），
> 不许直接改行。守卫 `node scripts/check/floor-guard.mjs` 会在 diff 里盯住这些动作。

Last reviewed: 2026-02-14（初版，基线数字为当日实测）

## 地板规则（Floor，永远阻断，零依赖）

- 不新增静音注释：`@ts-ignore`、`@ts-expect-error`、`eslint-disable`、`# noqa`、`# type: ignore` 等
- 不留半成品：空 `catch {}`、`except Exception: pass`、占位 `TODO`/`FIXME`
- 不跳过、不删除测试（要动，说明理由进提交信息或走例外表）
- 源码里不出现密钥
- 本文件不因某次改动而放水

检查者：`scripts/check/floor-guard.mjs`（diff 域，只看新增/删除行 + 未跟踪文件，
退出码 0/1/2，2 = 跑不了，不算干净）。本地 / CI 均跑。

## 带数字的强制项

| 维度 | 规则 | 检查者 | 运行时机 | 状态 |
|------|------|--------|----------|------|
| 类型 | 零 tsc 错误 | `pnpm build`（内含 tsc） | 每次 CI / 提交前 | 阻断 |
| Lint (py) | ruff 零错误 | `ruff check packages-py --select E4,E7,E9,F` | CI / 提交前 | 阻断 |
| 测试 (FE) | vitest 全绿 | `pnpm test` | CI / 提交前 | 阻断 |
| 测试 (py) | pytest 全绿（除 integration） | `uv run pytest packages-py/api/tests -m "not integration"` | CI / 提交前 | 阻断 |
| 分层 | §2 分层规则机械子集（agent/tools 禁直连浏览器与存储；crawler 禁直 import playwright） | `node scripts/check/layers-guard.mjs` | CI / 提交前 | **警告**（观察期，两周后转阻断） |
| 密钥 | 无泄漏 | gitleaks（CI observe job） | CI | **警告**（观察期） |
| 依赖安全 | high 以上不增长，逐步清零 | `pnpm audit --prod`（CI observe job） | CI | **阻断**（2026-02-14 已清零） |
| 性能/可访问性 | LCP ≤ 2500ms、CLS ≤ 0.1；axe critical/serious = 0 | lighthouse / axe 对本地 `:1420`（工具未装，装好后回填命令） | 本地预览，手动 | **警告**（未接线） |

策略（2026-02-14 起）：**地板与既有 CI 门禁阻断；新接入的检查警告两周**，观察无
误报后把上表「警告」改「阻断」。改状态 = 收紧，守卫不会拦。

## 已测量、暂不强制（棘轮：只锁不降）

| 指标 | 今日（2026-02-14） | 方向 |
|------|--------------------|------|
| 前端覆盖率（vitest --coverage，Lines / Branches） | 100% / 91.28% | 不得下降 |
| Python 覆盖率（pytest-cov，11 包汇总） | 64%（12177 语句 / 4434 未覆盖） | 不得下降；新代码走「变更行 ≥ 80%」 |
| `pnpm audit --prod` | 24 项（3 low / 11 moderate / 9 high / 1 critical） | 不得增长，只减不增 |
| 前端产物 dist/assets/*.js 总字节 | 1 022 432（≈ 998 kB） | 不得增长 |
| Rust | `cargo check --workspace --all-targets` 通过；`cargo test --workspace` 32 用例全绿（CI 已接线） | 不得出现失败用例 |

复测命令：

```bash
pnpm exec vitest run --coverage --coverage.reporter=text-summary
uv run --with pytest-cov pytest packages-py/api/tests -m "not integration" \
  --cov=api --cov=agent --cov=tools --cov=crawler --cov=browser \
  --cov=channels --cov=domains --cov=core --cov=contracts --cov=cli \
  --cov=infrastructure --cov-report=term -q | tail -3
pnpm audit --prod | tail -3
pnpm build && find apps/web/dist -name '*.js' -exec du -cb {} + | tail -1
```

## 本地检查分级（90 秒预算）

```bash
pnpm check:fast   # < 5s：floor-guard + layers-guard，写完每个文件随手跑
pnpm test         # < 5s：vitest；python: uv run pytest …（27s）→ 两者合计 < 90s
# check:full = CI：以上 + gitleaks + pnpm audit + cargo check
```

成本分级决定位置：秒级进编辑循环，半分钟进任务收尾，分钟级只进 CI。

## 例外表

| ID | 规则 | 路径 | 原因 | 负责人 | 过期 |
|----|------|------|------|--------|------|

（空。加例外 = 在此加一行 W/E 编号，守卫会盯住过期与未授权新增。）
