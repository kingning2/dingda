---
name: frontend-coding
description: 叮答前端编码范例。编写或修改 apps/web/ 与 packages/client/ 下 TypeScript / React 时必须遵循本 Skill 中的示例：文件粒度（一个功能块一个文件）、同类归文件夹、文件头与符号注释、命名、拆分阈值。架构与依赖方向见 frontend-architecture。
---

# 前端编码范例（照抄结构）

写 `apps/web/**` 与 `packages/client/**` 的 `.ts` / `.tsx` 时**按下面示例的形状写**，不要自创风格。
**架构与依赖方向不在本文件**，见 [frontend-architecture](../frontend-architecture/SKILL.md) 与 [layers.md](../layers.md)。

---

## 总纲：一个功能块 = 一个文件

**功能块** = 一个内聚的能力，能用**一句话**说清它解决什么问题。

判定它是不是「一个」功能块，用两把尺子：

1. **一句话测试**：说这句话时，需不需要用「和 / 以及 / 顺便」把几件事串起来？
   需要 → 它是多个功能块，应拆。
2. **数值阈值**（任一命中就检查是否混装）：

   | 信号 | 阈值 |
   |------|------|
   | 文件行数 | > 250 行 |
   | 顶层导出 | > 8 个 |
   | 文件头「职责：」 | 两行写不完 |

行数超阈值但**确实是单一职责**时，允许保留，但必须在文件头 `设计说明：` 里写明为什么不能拆。

### 错误示范（禁止）

```ts
// ❌ agent-runtime.ts —— 432 行 / 14 个导出，混装四类职责
export async function listAgentRuntimes() {}        // 探测
export async function probeAgentRuntime() {}        // 探测
export function buildAuthView() {}                  // 鉴权视图
export async function loginAgentRuntime() {}        // 登录
export async function downloadAgentRuntime() {}     // 下载
export function normalizeAgentRuntimeItem() {}      // 数据规整
```

一句话说不清它干什么 —— 「探测、鉴权、登录、下载」。这是四件事，必须拆。

---

## 示例 A：文件头 + 符号注释

**每个 `.ts` / `.tsx` 文件顶部必须有块注释**，形状固定为「一行总述 + `职责：` +（按需）`设计说明：`」。
只有一行总述 = 不合格。

```ts
/**
 * 外部 CLI Agent 的登录与鉴权视图。
 *
 * 职责：
 *   拉起 CLI 的登录流程，并把探针返回的鉴权结果组装成 UI 可直接渲染的鉴权视图。
 *
 * 设计说明：
 *   - 平台触发不了登录时返回 null，不臆造「需配置」态
 *   - 桌面走 Tauri invoke；非桌面不可达，不提供 mock 分支
 */

import type { AgentRuntimeItem, AgentRuntimeAuthView } from "@v2/contracts/agent-runtime";

/**
 * 拉起 CLI 登录。
 *
 * 返回 started=false 时 message 是给用户看的失败原因，调用方直接展示即可。
 */
export async function loginAgentRuntime(agentId: string): Promise<AgentRuntimeLoginResult> {
  // ...
}

/**
 * 把探针的鉴权结果组装成鉴权视图。
 *
 * `authenticated === null` 表示探针没给出结论（CLI 不支持登录探针），
 * 这时不能假定「未登录」，只能返回「未检测」或 null。
 */
export function buildAuthView(
  agent: Pick<AgentRuntimeItem, "name" | "can_login">,
  authenticated: boolean | null,
): AgentRuntimeAuthView | null {
  // ...
}
```

### 注释写什么

| 写 | 不写 |
|----|------|
| **为什么**这么设计、边界在哪、踩过的坑 | 复述代码在做什么 |
| 故障场景推理：「不设超时就会卡在 send() 上」 | 「本函数用于处理……」这类套话 |
| 非显然的取舍：「取 5s 是因为 punish 页常在正文渲染后 3s 才弹」 | 「计数器加一」贴在 `counter += 1` 上 |

常量表与映射表要写清「新增时只改这里」：

```ts
/**
 * Agent 运行阶段到 UI 的唯一映射。
 *
 * 新增阶段时只改这里，避免状态判断散落在 reducer、scheduler 和块组件中。
 */
export const AGENT_RUN_PHASE_MAP: Record<AgentRunPhase, AgentRunPhaseView> = { /* ... */ };
```

### 内部辅助函数

名字已自解释的可以省略注释；**有非显然取舍时必须写**。

---

## 示例 B：把一个混装文件拆成多个功能块

`agent-runtime.ts`（432 行）混装四类职责，拆成四个文件，每个文件头一句话说得清：

```text
cli/probe.ts       探测：本机装了哪些 CLI、能不能用、有哪些模型
cli/login.ts       登录：拉起 CLI 登录并组装鉴权视图
cli/download.ts    下载：把 CLI 装到叮答托管目录
cli/normalize.ts   规整：把后端/Rust 返回的原始字段收成 AgentRuntimeItem
```

拆完的验收标准：

- [ ] 每个新文件头「职责：」能用一句话说完，且不含「和」
- [ ] 每个新文件行数 ≤ 250
- [ ] 拆完**直接改调用方**，不留 `export { ... } from "./old"` 转发壳
- [ ] 被拆掉的原文件删除，不保留

### 错误示范（禁止）

```ts
// ❌ 转发壳：把环藏在转发层里，依赖图凭空多一条边
export { loginAgentRuntime } from "./cli/login";
export { probeAgentRuntime } from "./cli/probe";
```

```ts
// ❌ 拆成参数化巨型函数，用布尔开关区分行为
export async function handleAgentAction(action: "login" | "download" | "probe") {}
```

---

## 示例 C：同类归文件夹

**文件夹只在同类文件 ≥ 2 个时建立**；只有 1 个文件的类别放包根。

```text
packages/client/ui-agent/src/
  index.ts                 包入口（只暴露应用层要装配的东西）
  api.ts                   单文件功能块 → 放包根，不建文件夹
  cli/                     同类：外部 CLI Agent 能力（6 个文件）
    catalog.ts
    probe.ts
    login.ts
    download.ts
    normalize.ts
    scan.ts
  run/                     同类：一次 Agent 运行（3 个文件）
    stream.ts
    phase.ts
    reducer.ts
  ui/                      同类：本包的 React 组件（3 个文件）
    runtimes-panel.tsx
    runtime-card.tsx
    icon.tsx
```

### 文件夹命名规则

1. **文件夹名 = 类别名**，必须是**业务概念或机制名**（`cli/` `run/` `ui/`）。
2. **禁止垃圾桶名**：`utils/` `helpers/` `services/` `common/` `misc/` `shared/` `lib/`。
   命中这些名字说明你没想清这一类是什么。
3. **文件名不重复文件夹名**：`run/run.ts` ✗ → `run/stream.ts` ✓。
4. **不建包内桶文件**：`cli/index.ts` 再 `export *` 一遍是转发壳，禁止。
   消费方写全路径 `@v2/ui-agent/cli/probe`。
5. **每个有代码的文件夹必须有 `README.md`**（树形：上层只链下层）。

### 包入口 `index.ts` 只放「应用层要装配的东西」

包入口是给 `apps/web` 用的。**内部互相引用一律走相对路径**，不要绕回包入口。

```ts
// ✅ 包入口只暴露应用层要装配的面板
export { AgentRuntimesPanel } from "./ui/runtimes-panel";
```

```ts
// ❌ 把内部实现细节也挂到包入口，等于给每个符号留一条对外通路
export { AgentRuntimeCard } from "./ui/runtime-card";
export { AGENT_CATALOG } from "./cli/catalog";
export { loadCachedAgentRuntimes, probeSingleAgent /* ... */ } from "./cli/scan";
```

---

## 命名速查

| 位置 | 正确 | 错误 |
|------|------|------|
| 文件（逻辑） | `agent-runtime-scan.ts` `run-phase.ts` | `scan.ts` `utils.ts` `helpers.ts` |
| 文件（组件） | `agent-runtime-card.tsx` | `card.tsx` `Component.tsx` |
| 文件夹 | `cli/` `run/` `ui/` | `utils/` `common/` `services/` |
| 组件 | `AgentRuntimeCard` | `Card` `AgentRuntimeCardComponent` |
| 逻辑 / 工具 | `probeAgentRuntime` | `doProbe` `handleProbe2` |
| 类型 | `AgentRuntimeItem` `SetupPhase` | `IData` `IResult` `Props2` |

**禁止泛化命名**：`data2`、`resultFinal`、`handleClick2`、`newFunction`、`temp`。

---

## 目录 README（树形，上层引用下层）

每个**有代码的文件夹**必须有 `README.md`。形状：

1. 一行总述本目录 / 本包职责
2. **本目录文件**：每个 `.ts` / `.tsx` 一条，写清：**干什么、关键符号、谁调用**。
   禁止只写裸路径 —— 读者没看过代码也要能知道该打开哪个文件
3. **子目录**：相对链接指向下层 `README.md`，不要把子目录每个文件抄进上层
4. 禁止另起一套地图；文件级细节以下层 README 为准

```markdown
## 文件

- `src/cli/probe.ts` — 探测本机装了哪些 CLI、能否可用、有哪些模型。
  关键符号：`listAgentRuntimes` / `probeAgentRuntime` / `probeAgentsInBackground`。
  调用：`cli/scan.ts`、`ui/runtime-card.tsx`。
```

不要只写「`src/probe.ts` — 探测」。**「谁调用」必须用 Grep 实证，不靠猜。**

新增目录时：**先写下层 README，再在上层「子目录」里加一行链接**。改职责时同步该层 README。

---

## 检查清单（交代码前）

- [ ] 文件顶部有块注释，且「职责：」能用一句话说完、不含「和」
- [ ] 文件 ≤ 250 行、顶层导出 ≤ 8 个（超了要写明为什么不能拆）
- [ ] 每个导出符号有注释，写的是「解决什么问题」而非复述签名
- [ ] 注释里有故障场景推理，没有「本函数用于处理…」这类套话
- [ ] 同类文件已归入文件夹；文件夹名不是垃圾桶名
- [ ] 文件名不重复文件夹名；没有 `cli/index.ts` 这类桶文件
- [ ] 包入口只暴露应用层要装配的东西；内部引用走相对路径
- [ ] 拆 / 改名后**直接改了调用方**，没有留转发壳
- [ ] 本目录 `README.md` 已更新；上层 README 已链接到本目录
- [ ] 跑过 `pnpm check:deps`、`pnpm check:unused`、`pnpm exec tsc --noEmit`

---

## 第一个应用：`packages/client/ui-agent`

当前 11 个文件平铺在 `src/` 下，其中 `agent-runtime.ts`（432 行 / 14 导出）混装四类职责。
按本 Skill 的目标结构：

```text
ui-agent/src/
  index.ts                    包入口（只暴露 AgentRuntimesPanel）
  api.ts                      Agent 域 Server HTTP（偏好 / 目录 / 工作会话）
  cli/
    catalog.ts                支持的 Agent 白名单（与后端 / Rust registry 对齐）
    probe.ts                  探测
    login.ts                  登录与鉴权视图
    download.ts               下载
    normalize.ts              数据规整
    scan.ts                   发现编排（缓存 → 后台补探测 → 手动全量扫描）
  run/
    stream.ts                 SSE 收发
    phase.ts                  阶段映射
    reducer.ts                事件折叠
  ui/
    runtimes-panel.tsx        Agent 页主面板
    runtime-card.tsx          单个 Agent 的配置卡
    icon.tsx                  Agent 图标
```

改造分两步走（见 `.workbuddy-ai/outputs/ui-agent-refactor-plan.md`）：
先补文档与注释，再拆 `agent-runtime.ts` 并改调用方。
