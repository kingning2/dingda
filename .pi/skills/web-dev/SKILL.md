---
name: web-dev
description: 叮答前端（apps/web + packages/，React 19 + Tailwind v4，pnpm workspace）编码规范。写或改前端时使用：装配层与 16 个 @v2 包各自收什么、怎么被消费（真实用法示例）、guards 字段容错、三条结构纪律与验证命令。
---

# 前端编码规范（apps/web + packages/）

## 1. 语言通用（写任何文件之前）

1. **一个功能块一个文件**：超过 250 行或 8 个导出就拆；同类归文件夹（`run/` 收流式相关）。
2. **文件头**：`/** 职责 / 设计说明 */` 块注释，写「解决什么问题」不复述签名。
   范本：`packages/client/runtime/src/guards.ts`。
3. **命名无例外**：

| 对象 | 规则 | ✓ | ✗ |
|------|------|---|---|
| 文件 / 目录 | kebab-case | `accounts-page.tsx` | `AccountsPage.tsx` |
| 组件符号与 JSX 标签 | PascalCase | `<AccountsPage />` | `<accountsPage />` |
| 变量 / 函数 / props | 小驼峰 | `recentWorks` | `recent_works` |
| hooks | `use` 前缀 | `useRunStream` | `runStream()` |
| 第三方 import | 保留原始导出名 | `import { cn } from "@v2/ui-primitives/utils"` | `import { cn as joinCls }` |

   已存在的例外**不作为新代码的参考依据**。
4. **字段容错**：后端字段一律经 `@v2/runtime/guards` 判定后使用，不裸取。
5. **纯逻辑与纯组件优先**：能不碰 React 状态就不碰；可单测的放进 `tests/`。
6. **测试**：与被测代码同包，放 `tests/`（vitest）。

✓ 示例（guards 形状，范本 `runtime/src/guards.ts`）：

```ts
/** 从未知载荷里安全取字符串字段，取不到给兜底。 */
const title = isString(payload.title, "");
const candidates = isArray(payload.items, []) && payload.items;
```

✗ 反例：

```tsx
const title = payload.title as string;        // 禁断言绕过
const data2 = res.data ?? {};                 // 禁 data2
<div>{loading ? <accountsPage/> : null}</div> // 小写标签=DOM 字符串标签，是 bug
```

## 2. 包地图与依赖单向流

```
apps/web（装配层）
  → ui-home ui-ai ui-composer ui-account ui-agent ui-crawler ui-watch ui-workflow（业务域）
    → ui-layout（外壳导航） ui-feedback（错误边界）
      → ui-primitives（原子组件 + cn()）
        → ui-theme（设计令牌）
叶子：contracts（线协议） routes（paths.ts） app-state（跨域 zustand） runtime（http/guards/能力）
```

**三条结构纪律**（违反 = 打回）：

1. 业务域包互不横引（ui-agent 不 import ui-crawler）；跨域组合只允许在 `apps/web` 装配层。
2. 两个以上域要用的状态/组件**下沉**到底层包（runtime / primitives），不在域包间转发。
3. 包不 import 应用源码；应用（apps/web）可以 import 一切。
   实证：`boot-gate.tsx` 头注——它要调 ui-agent/ui-account 的发现逻辑，
   若留在 runtime 就成了「基座依赖业务」，所以移到应用装配层。

## 3. apps/web（装配层）

```
apps/web/src/
├── main.tsx / App.tsx    # 入口与 Provider 装配
├── boot/                 # 启动编排（跨域组合唯一合法点）：boot-gate.tsx / preload.ts / alert-navigator.ts
├── pages/                # 页面级组件 <域>-page.tsx
└── routes/
    ├── pages/<域>-route.tsx
    └── layouts/
```

✓ 页面 = 业务包的装配壳（实证 `pages/accounts-page.tsx`）：

```tsx
import { AccountsHub } from "@v2/ui-account";

/** 平台账号页（闲鱼 / 小红书 / 1688）。 */
export function AccountsPage() {
  return (
    <section>
      <AccountsHub />
    </section>
  );
}
```

✓ 启动闸门（实证 `boot/boot-gate.tsx`）：`useServer()` 看状态 → 预载首页数据 →
`dismissBootSplash()` 放行；跨域调用只允许出现在 boot/ 这一层。

**新增页面三步**：`pages/<域>-page.tsx` → `routes/pages/<域>-route.tsx` →
`@v2/routes` 的 `paths.ts` 登记路径常量。

## 4. 叶子四包（怎么被消费）

### contracts（`packages/contracts`）

与 `packages-py/contracts` 对齐的 TS 类型，**按域一文件**（`ai-work.ts`、`watch.ts`…）：

```ts
import type { AgentWorkDetailView, AgentWorkSummary } from "@v2/contracts/ai-work";
```

注意：纯类型零运行时；改字段先改两侧契约（AGENTS.md 4.6）。

### routes

路径常量唯一来源（实证 `routes/src/paths.ts`）：

```ts
import { paths } from "@v2/routes";
navigate(paths.accounts);
```

注意：只放常量与 `EntryView` 之类的视图类型；`paths` 里不写函数。

### app-state

跨域共享 zustand store（实证 `discovery-store.ts`）——**store 定义、组件订阅、
逻辑文件写 setter** 三种用法：

```ts
// ① 组件里订阅
const recentWorks = useDiscoveryStore((s) => s.recentWorks);
// ② 非组件逻辑里写状态（实证 recent-works.ts）
const { setRecentWorks, setRecentWorksLoading } = useDiscoveryStore.getState();
```

注意：域内私有状态不上浮到这里；新 store 一文件，从 `index.ts` 出口。

### runtime

HTTP 出口唯一（实证 `http-client.ts` / `ui-agent/src/api.ts`）：

```ts
import { api } from "@v2/runtime/http-client";

const { data, response } = await api.get<AgentWorkDetailResponse>(
  `/v1/agent/works/${encodeURIComponent(workId)}`,
  { baseUrl: options?.baseUrl, fallbackError: "读取工作对话失败", allowStatuses: [404] },
);
if (response.status === 404) return null;
```

宿主能力（实证 `capabilities.ts`）——**禁止散落 `isTauri()` 分支**：

```ts
import { getHostCapabilities } from "@v2/runtime/capabilities";
const { desktop, windowChrome } = getHostCapabilities(); // 壳注入的能力开关
```

其余出口：`guards.ts`（字段容错）、`app-alert.ts`（全局提示订阅，给 ui-feedback 消费）、
`server-provider.tsx`（`useServer()`）、`error-reporting.ts`。
注意：业务模块只调 `api.get/put/...`，**不要各自 fetch**；Web 默认 base
`VITE_API_BASE_URL` 或 `http://127.0.0.1:8787`，桌面由 ServerProvider 注入。

## 5. 底座四包（怎么被消费）

### ui-theme

设计令牌入口 `theme.css`：`@import "tailwindcss"` + `tokens.css` + `@theme` 块。

⚠ **新增一级包目录必须回 ui-theme 补一行 `@source`**（实证文件头注释：Vite 根在仓库根，
自动扫描对 pnpm 软链时灵时不灵；漏了不报错，只会悄悄不生成那些类）：

```css
@source "../../../../packages";
@source "../../../../apps";
```

注意：组件里颜色/间距只引令牌类，不写魔法值。

### ui-primitives

原子组件**按文件导出**（实证），`cn()` 在 `utils`：

```tsx
import { cn } from "@v2/ui-primitives/utils";
import { Button } from "@v2/ui-primitives/button";
import { Alert, AlertTitle, AlertDescription } from "@v2/ui-primitives/alert";
```

注意：无业务词；新原子组件一文件，别往 `index` 塞桶导出（本包就没有 index.ts）。

### ui-layout

外壳导航（实证文件：`app-shell` `entry-shell` `workspace-shell` `page-header`
`entry-nav-rail` `title-bar` `animated-outlet`）：在 `apps/web/src/routes/layouts/`
装配；壳组件内部用 `cn()` 合 className，不 import 业务域包。

### ui-feedback

错误边界与全局提示（实证：`app-alert-host.tsx` `app-error-boundary.tsx`）：

```tsx
import { AppAlertHost } from "@v2/ui-feedback"; // 挂在应用装配层，全局一次
// 业务里发提示走 runtime 出口，不直接操作 DOM：
import { showAppAlert } from "@v2/runtime/app-alert";
```

注意：文案与展示样式收敛在这里；业务包只声明语义。

## 6. 业务域八包（同构模板 + 差异）

每包同构（实证范本 `packages/client/ui-agent/`）：

```
packages/client/ui-<域>/src/
├── index.ts          # 公开出口（包外只准从这里 import）
├── api.ts            # 该域的 Server 调用（经 @v2/runtime http-client）
├── <功能>.ts          # 一个功能块一个文件（recent-works.ts 预热、status-tone.ts 展示口径）
├── <功能>/            # 流式等成组逻辑收文件夹（run/：phase reducer stream）
└── tests/            # vitest
```

✓ 域包内「调 API + 写共享 store」组合（实证 `ui-agent/src/recent-works.ts`）：

```ts
import { useDiscoveryStore } from "@v2/app-state";
import { fetchAgentWorkList } from "./api";

export async function refreshRecentWorks(options?: { limit?: number }): Promise<void> {
  const { setRecentWorks, setRecentWorksLoading } = useDiscoveryStore.getState();
  setRecentWorksLoading(true);
  try {
    setRecentWorks(await fetchAgentWorkList({ limit: options?.limit ?? 40 }));
  } catch {
    setRecentWorks([]);
  }
}
```

| 包 | 域 | 特别注意 |
|----|----|----------|
| `ui-home` | 首页 | 只装配展示，重逻辑下沉 |
| `ui-ai` | 对话/生成 | 流式状态经 reducer，不在组件里攒 |
| `ui-composer` | 创作编排 | 大表单拆子组件文件 |
| `ui-account` | 账号 | 平台枚举与 channels/api 对齐 |
| `ui-agent` | 任务/作品 | api/recent-works/run 流是范本 |
| `ui-crawler` | 爬虫监控 | 只读展示任务状态，不直接碰浏览器概念 |
| `ui-watch` | 监控 | 轮询经 app-state 计时，不散 setInterval |
| `ui-workflow` | 工作流画布 | 节点类型收 `types` 文件，别散在组件里 |

## 7. 验证要求（交码前必跑）

```bash
pnpm --filter @dingda/web exec tsc --noEmit   # 或按仓库别名 tsc -p apps/web
pnpm check:deps
pnpm check:unused --strict
pnpm test                                     # vitest
pnpm check:fast                               # 守卫总闸（< 5s）
```
