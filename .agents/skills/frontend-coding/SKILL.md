---
name: frontend-coding
description: 前端（TypeScript / React）编码规范模板。写或改前端代码时按本文件的示例形状落笔：文件粒度（一个功能块一个文件）、同类归文件夹、文件头与符号注释、命名、字段容错、拆分阈值。本文件与具体项目无关，可直接复制到其他项目使用；项目特有的落点（源码根、共享模块路径、检查命令）写在项目自己的规则文件里。
---

# 前端编码规范（模板）

写 `.ts` / `.tsx` 时**按下面示例的形状写**，不要自创风格。

**本文件是通用模板，不含任何项目路径。** 示例里的包名、模块名、类型名都是占位。
项目特有的落点写在项目自己的规则文件里（例如 `.cursor/rules/<项目>-frontend.mdc`）：

- 源码根在哪、有哪些包
- 共享模块叫什么（判定器、HTTP 客户端、状态库……）
- 交代码前跑哪些命令

> 往本文件里加项目路径之前先想清楚：加了之后它就不能直接复制到别的项目了。
> 项目落点写到项目规则文件去。

**架构与依赖方向不在本规范** —— 那是项目自己的事，见项目的架构文档。

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
// ❌ tool-runtime.ts —— 432 行 / 14 个导出，混装四类职责
export async function listToolRuntimes() {}         // 探测
export async function probeToolRuntime() {}         // 探测
export function buildAuthView() {}                  // 鉴权视图
export async function loginToolRuntime() {}         // 登录
export async function downloadToolRuntime() {}      // 下载
export function normalizeToolRuntimeItem() {}       // 数据规整
```

一句话说不清它干什么 —— 「探测、鉴权、登录、下载」。这是四件事，必须拆。

---

## 示例 A：文件头 + 符号注释

**每个 `.ts` / `.tsx` 文件顶部必须有块注释**，形状固定为「一行总述 + `职责：` +（按需）`设计说明：`」。
只有一行总述 = 不合格。

```ts
/**
 * 外部工具的登录与鉴权视图。
 *
 * 职责：
 *   拉起外部工具的登录流程，并把探针返回的鉴权结果组装成 UI 可直接渲染的鉴权视图。
 *
 * 设计说明：
 *   - 平台触发不了登录时返回 null，不臆造「需配置」态
 *   - 桌面走原生桥；非桌面不可达，不提供 mock 分支
 */

import type { ToolRuntimeItem, ToolAuthView } from "<类型包>";

/**
 * 拉起外部工具登录。
 *
 * 返回 started=false 时 message 是给用户看的失败原因，调用方直接展示即可。
 */
export async function loginToolRuntime(toolId: string): Promise<ToolLoginResult> {
  // ...
}

/**
 * 把探针的鉴权结果组装成鉴权视图。
 *
 * `authenticated === null` 表示探针没给出结论（该工具不支持登录探针），
 * 这时不能假定「未登录」，只能返回「未检测」或 null。
 */
export function buildAuthView(
  tool: Pick<ToolRuntimeItem, "name" | "can_login">,
  authenticated: boolean | null,
): ToolAuthView | null {
  // ...
}
```

### 注释写什么

| 写 | 不写 |
|----|------|
| **为什么**这么设计、边界在哪、踩过的坑 | 复述代码在做什么 |
| 故障场景推理：「不设超时就会卡在 send() 上」 | 「本函数用于处理……」这类套话 |
| 非显然的取舍：「取 5s 是因为风控页常在正文渲染后 3s 才弹」 | 「计数器加一」贴在 `counter += 1` 上 |

常量表与映射表要写清「新增时只改这里」：

```ts
/**
 * 运行阶段到 UI 的唯一映射。
 *
 * 新增阶段时只改这里，避免状态判断散落在 reducer、视图层与块组件中。
 */
export const RUN_PHASE_MAP: Record<RunPhase, RunPhaseView> = { /* ... */ };
```

### 内部辅助函数

名字已自解释的可以省略注释；**有非显然取舍时必须写**。

---

## 示例 B：把一个混装文件拆成多个功能块

`tool-runtime.ts`（432 行）混装四类职责，拆成四个文件，每个文件头一句话说得清：

```text
integration/probe.ts       探测：本机装了哪些外部工具、能不能用、有哪些版本
integration/login.ts       登录：拉起外部工具登录并组装鉴权视图
integration/download.ts    下载：把工具装到应用托管目录
integration/normalize.ts   规整：把后端返回的原始字段收成 ToolRuntimeItem
```

拆完的验收标准：

- [ ] 每个新文件头「职责：」能用一句话说完，且不含「和」
- [ ] 每个新文件行数 ≤ 250
- [ ] 拆完**直接改调用方**，不留 `export { ... } from "./old"` 转发壳
- [ ] 被拆掉的原文件删除，不保留

### 错误示范（禁止）

```ts
// ❌ 转发壳：把环藏在转发层里，依赖图凭空多一条边
export { loginToolRuntime } from "./integration/login";
export { probeToolRuntime } from "./integration/probe";
```

```ts
// ❌ 拆成参数化巨型函数，用布尔开关区分行为
export async function handleToolAction(action: "login" | "download" | "probe") {}
```

---

## 示例 C：同类归文件夹

**文件夹只在同类文件 ≥ 2 个时建立**；只有 1 个文件的类别放包根。

```text
<包根>/src/
  index.ts                 包入口（只暴露应用层要装配的东西）
  api.ts                   单文件功能块 → 放包根，不建文件夹
  integration/             同类：外部工具集成（6 个文件）
    catalog.ts
    probe.ts
    login.ts
    download.ts
    normalize.ts
    scan.ts
  run/                     同类：一次运行（3 个文件）
    stream.ts
    phase.ts
    reducer.ts
  ui/                      同类：本包的 React 组件（3 个文件）
    panel.tsx
    card.tsx
    icon.tsx
```

### 文件夹命名规则

1. **文件夹名 = 类别名**，必须是**业务概念或机制名**（`integration/` `run/` `ui/`）。
2. **禁止垃圾桶名**：`utils/` `helpers/` `services/` `common/` `misc/` `shared/` `lib/`。
   命中这些名字说明你没想清这一类是什么。
3. **文件名不重复文件夹名**：`run/run.ts` ✗ → `run/stream.ts` ✓。
4. **不建包内桶文件**：`integration/index.ts` 再 `export *` 一遍是转发壳，禁止。
   消费方写全路径 `<包名>/integration/probe`。
5. **每个有代码的文件夹必须有 `README.md`**（树形：上层只链下层）。

### 包入口 `index.ts` 只放「应用层要装配的东西」

包入口是给应用装配层用的。**内部互相引用一律走相对路径**，不要绕回包入口。

```ts
// ✅ 包入口只暴露应用层要装配的面板
export { ToolRuntimesPanel } from "./ui/panel";
```

```ts
// ❌ 把内部实现细节也挂到包入口，等于给每个符号留一条对外通路
export { ToolRuntimeCard } from "./ui/card";
export { TOOL_CATALOG } from "./integration/catalog";
export { loadCachedToolRuntimes, probeSingleTool /* ... */ } from "./integration/scan";
```

---

## 命名速查

| 位置 | 正确 | 错误 |
|------|------|------|
| 文件（逻辑） | `tool-runtime-scan.ts` `run-phase.ts` | `scan.ts` `utils.ts` `helpers.ts` |
| 文件（组件） | `tool-runtime-card.tsx` | `card.tsx` `Component.tsx` |
| 文件夹 | `integration/` `run/` `ui/` | `utils/` `common/` `services/` |
| 组件 | `ToolRuntimeCard` | `Card` `ToolRuntimeCardComponent` |
| 逻辑 / 工具 | `probeToolRuntime` | `doProbe` `handleProbe2` |
| 类型 | `ToolRuntimeItem` `SetupPhase` | `IData` `IResult` `Props2` |

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

- `src/integration/probe.ts` — 探测本机装了哪些外部工具、能否可用、有哪些版本。
  关键符号：`listToolRuntimes` / `probeToolRuntime` / `probeToolsInBackground`。
  调用：`integration/scan.ts`、`ui/card.tsx`。
```

不要只写「`src/probe.ts` — 探测」。**「谁调用」必须用 Grep 实证，不靠猜。**

新增目录时：**先写下层 README，再在上层「子目录」里加一行链接**。改职责时同步该层 README。

---

## 示例 D：字段级容错用判定器，不写类型判定型三元

后端 / 外部 CLI / `sessionStorage` 给的字段，形状不保证。这类「判定 + 兜底」不要写
`typeof x === "string" ? x : ""`，用项目里的共享判定器模块：

```ts
import { isArray, isObject, isString } from "<判定器模块>";

// ✗ 判定型三元；嵌套两层之后基本读不动
seller: typeof item.supplier === "string" ? item.supplier : null,
product_url:
  typeof item.url === "string" ? item.url
  : typeof item.product_url === "string" ? item.product_url
  : undefined,

// ✓ 一次调用；多候选按顺序取第一个通过的
seller: isString(item.supplier, null),
product_url: isString([item.url, item.product_url], undefined),
```

**返回类型由兜底值决定**：`isString(x, "")` → `string`；`isString(x, null)` →
`string | null`；`isString(x, undefined)` → `string | undefined`。不需要在调用点标注。

### 判定器模块的形状（项目里没有就照这个建）

关键在**用一个工厂派生全部判定器**，而不是给每个类型手写一遍候选遍历：

```ts
/** 类型谓词。 */
export type TypeGuard<T> = (value: unknown) => value is T;

/**
 * 取值器工厂：给一个判定，得到「按顺序取第一个满足判定的候选值，否则兜底」的函数。
 * 返回类型 `T | F` 由兜底值决定，所以调用点不用标注。
 */
export function picker<T>(guard: TypeGuard<T>) {
  return <F>(values: unknown, fallback: F): T | F => {
    // 先整体：整个值满足判定就直接用它
    if (guard(values)) return values;
    // 再逐元素：整体不满足、且它是数组时，才当候选列表按顺序找（见下方边界 2）
    if (Array.isArray(values)) {
      for (const candidate of values) if (guard(candidate)) return candidate;
    }
    return fallback;
  };
}

export const isString = picker<string>((v): v is string => typeof v === "string");
export const isNumber = picker<number>(
  (v): v is number => typeof v === "number" && Number.isFinite(v),
);
export const isBoolean = picker<boolean>((v): v is boolean => typeof v === "boolean");
export const isObject = picker<Record<string, unknown>>(
  (v): v is Record<string, unknown> =>
    typeof v === "object" && v !== null && !Array.isArray(v),
);
export const isArray = picker<unknown[]>((v): v is unknown[] => Array.isArray(v));
export const isFunction = picker<(...args: never[]) => unknown>(
  (v): v is (...args: never[]) => unknown => typeof v === "function",
);
```

两个判定器值得注意：

- `isNumber` 拒掉 `NaN` 与 `±Infinity` —— 它们 `typeof` 是 `"number"`，但流到下游会算出 `NaN` 并一路传染。
- `isObject` 排除 `null` 与数组 —— 三者 `typeof` 都是 `"object"`，但只有普通对象能当字段容器。

### 三条使用边界（写错会引入 bug）

1. **判定器不转换。** `isNumber("12")` 是 `false`。要「尽量救回来」用转换函数
   （如 `asNumber`）。两者语义不同：判定是「信任这个值」，转换是「尽量救回来」。
   把 `String(item.id)` 改成 `isString(item.id, "")` 会让数字 id 静默变成空串。
2. **数组先整体、再逐元素。** 整个值满足判定就直接用它；不满足、且它是数组时，才当候选列表
   按顺序找。所以 `isString([a, b], "")` 是「在 a、b 里找字符串」，而 `isArray(x, [])`
   是「`x` 本身是不是数组」。**这个顺序不能颠倒** —— 先逐元素的话，`isArray(items, [])`
   会去 `items` **里面**找数组，让「取一个数组字段」这个最常见写法静默拿到兜底值。
3. **输入已经是数组类型时不要用 `isArray`。** 例如
   `Array.isArray(data.items) ? data.items : []` 里 `data.items` 已声明为
   `Item[]`；`isArray` 会把元素类型退化成 `unknown`，反而要加断言。
   这种「已声明类型的运行时校验」保持原样更清楚。

### 不适用范围

普通的二选一分支 —— 两种载荷形状、JSX 条件渲染、`x ?? y` —— **不属于**这个模式，
仍该用 `if` / 三元。套判定器只会更绕。

**不要把这条推广成「禁止三元」。** 无差别推广会让 JSX 条件渲染被迫写成更绕的形式，
可读性反而下降。

---

## 检查清单（交代码前）

- [ ] 文件顶部有块注释，且「职责：」能用一句话说完、不含「和」
- [ ] 文件 ≤ 250 行、顶层导出 ≤ 8 个（超了要写明为什么不能拆）
- [ ] 每个导出符号有注释，写的是「解决什么问题」而非复述签名
- [ ] 注释里有故障场景推理，没有「本函数用于处理…」这类套话
- [ ] 同类文件已归入文件夹；文件夹名不是垃圾桶名
- [ ] 文件名不重复文件夹名；没有 `integration/index.ts` 这类桶文件
- [ ] 包入口只暴露应用层要装配的东西；内部引用走相对路径
- [ ] 拆 / 改名后**直接改了调用方**，没有留转发壳
- [ ] 字段容错用了项目的判定器模块，没写 `typeof x === "..." ? x : y`
- [ ] 本目录 `README.md` 已更新；上层 README 已链接到本目录
- [ ] 跑过项目规定的检查命令（类型检查 / 依赖检查 / 未使用导出检查，见项目规则文件）
